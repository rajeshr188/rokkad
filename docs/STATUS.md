---
status: active
owner: project
updated: 2026-08-17
tags: [status, architecture]
related: [ROADMAP.md, plans/completed.md, plans/active.md]
---

# Status

## 2026-08-17 — Phase 7 residue cleanup complete

The first Phase 7 slice removes `request.tenant` from middleware, templates,
and tests; `request.workspace` is now the only HTTP Workspace attribute. The
middleware API and diagnostic field now use Workspace terminology. Empty
django-tenants settings (`TENANT_APPS`, tenant model/domain settings,
public-schema URLConf, and the unused auto-seed flag) are removed. Guardian had
zero object-permission assignments and no runtime decorator callers, so its
installed app, backend, settings, object-permission decorator, and foundation
inventory branch are retired; `WorkspaceAccess` remains the authorization
authority. The stale invitation test contradiction is resolved in favor of the
accepted Phase 5 contract: the canonical alias preserves the key through login,
while the retired third-party route returns HTTP 410. System checks and
migration drift pass, and the first combined Phase 7 regression gate passes
155/155. Remaining Phase 7 work includes URLConf/package/schema terminology,
the unused Guardian dependency declaration in the UTF-16 requirements file,
and classification of legacy inbound routes.

The second slice makes `django_project.workspace_urls` the active shared-schema
business URLConf and removes the obsolete `tenant_urls` compatibility module
after moving all active imports and test overrides. Party portal identity now
reads only `request.workspace`, closing the last runtime `request.tenant`
consumer exposed by the regression gate. Route behavior is unchanged. The
`reset_sequences` command no longer accepts arbitrary schema or all-schema
options and operates only on the shared schema. Current public and Notify v2 UI
copy no longer advertises retired accounting or tenant-schema operation.

The third slice renames the active seed commands to
`seed_workspace_defaults` and `seed_all_workspaces`, updates their callers and
current documentation, and removes an unreachable Product-era seeding method.
No legacy command aliases remain.

The fourth slice inventories legacy inbound routes. Contact, Girvi, and legacy
Notify paths are project-owned redirects only; they do not participate in
Workspace resolution, authorization, or RLS context. The old dashboard and
integer-ID control-plane routes are likewise inbound compatibility surfaces.
All are deferred until telemetry or an explicit compatibility deadline supports
removal. The obsolete Guardian claim is removed from the README; only its
dependency line remains, blocked on safely normalizing the UTF-16 manifest.

The fifth slice classifies the final broad schema-era names. The
`apps.tenant_apps` package is deferred naming debt spanning 197 live files and
three migrations; a rename has no isolation benefit. `Company.schema_name` is
the current unique Workspace routing key, not database state. ADR
`2026-08-17-transitional-tenancy-names.md` requires a later additive,
backfilled, immutable `Company.slug` migration instead of an in-place rename.

The final slice normalizes `requirements.txt` from UTF-16 LE to UTF-8 and
removes the unused `django-guardian` declaration. Phase 7 is complete: no live
Guardian integration, `request.tenant`, tenant URLConf, django-tenants setting,
or tenant-named seed command remains. Deferred package/field names and inbound
aliases are explicitly classified rather than mistaken for runtime tenancy.

Phase 8 has started with an executable control-plane contract-test plan. It
will turn the accepted `CP-*` invariants into a traceable CI gate before Phase
9 app conformance work.

Phase 8.2 maps all 25 invariants to exact executable test labels and records
four honest coverage gaps rather than treating nearby module tests as proof.
New source guards enforce exclusive PostgreSQL context setting through
`workspace_context()` and prevent Party, Loans, Notify v2, and Rates from
importing subscription models, billing transitions, or provider services.

Phase 8.3 closes `CP-JOB-001`. Workspace seed fan-out and per-Workspace seed
execution now have direct explicit-ID/context tests. The audit found and fixed
`reassess_pawn_loans`, which accepted `--workspace-id` but previously required
an ambient context; the command now owns `workspace_context(workspace_id)`.

## 2026-08-17 — Phase 6 URL and control-plane UI standardization complete

The global shell remains rooted at `/app/`, while authenticated Workspace
navigation now emits canonical `/w/<workspace_slug>/...` URLs. Workspace
dashboard, settings, setup/state, team, invitation/new, modules, security,
billing, and archive surfaces resolve the explicit slug and render the existing
authorized target directly instead of bouncing through integer-ID URLs.
Workspace selection and invitation acceptance now land on the canonical slug
dashboard. Desktop/mobile settings navigation, Workspace cards, breadcrumbs,
quick actions, and HTMX invitation actions use the same route contract. Legacy
`/orgs/...` and `/workspace/<id>/...` entry points remain temporary inbound
compatibility surfaces; no live primary shell emits them for the standardized
flows. Focused URL, shell, navigation, and org regressions pass 114/114. The
broader suite has one unrelated pre-existing contradiction in the Phase 7
public invitation alias tests (one test expects the live alias to redirect to
login while another expects the same anonymous URL to return 410); Phase 6 did
not change that alias. Phase 7 residue cleanup is next.

## 2026-08-17 — Phase 5 invitation convergence complete

Phase 4 is checkpointed in commit `ec62c98`. Phase 5 now has one locked,
verified, idempotent invitation-acceptance command. It rejects mismatched or
unverified email, expiry, revoked/declined state, inactive Workspace state, and
seat-capacity failure before mutation; successful acceptance creates one
Membership and writes the terminal invitation state and audit evidence. Direct
email links are confirmation-only on GET and accept through CSRF-protected POST;
anonymous links preserve the key through login. Migration
`orgs.0004_retire_pending_invitation_bridge` is applied locally: bridge intent
is reconciled to authoritative invitations, orphans abort before deletion, and
the bridge table is retired. Signup and django-invitations signals no longer
create Membership implicitly. The obsolete signal-era tests are removed and
their replacement contract asserts that Membership receivers stay absent. The
final invitation, onboarding, source-contract, and org regression gate passes
138/138; foundation inventory reports zero integrity findings. Phase 6 URL and
control-plane UI standardization is next.

## 2026-08-17 — Phase 4 major acceptance review

The Workspace lifecycle, Subscription lifecycle, entitlement authority,
control-plane authorization, and forced-RLS foundation have been reviewed as a
single request boundary. A billing fail-open blocker was found in
`SubscriptionValidationMiddleware` and fixed: billing evaluation exceptions
now return HTTP 503. Full-client tests prove no Subscription is redirected to
Workspace billing, active/current-trial access is allowed, and expired trials
are recovery-only. The combined control-plane suite passes 141/141 and the
billing plus four-app restricted-role RLS gate passes 17/17. The classified
review is `docs/implementation/control-plane-phase4-major-review.md`. Phase 5
invitation/onboarding consolidation is next.

The post-review billing recovery check found an empty local Plan catalog. The
default catalog command is now idempotent, the local database has active
Starter, Professional, and Enterprise rows, and live plan copy no longer
advertises retired Product, Inventory/Warehouse, or invoice-era capacity.

Development now exposes explicit owner-only plan trial activation. Trial start
is POST-only, locks the Workspace, rejects duplicate subscriptions, creates the
BillingAccount and typed entitlement projection atomically, and appends a
`trial.started` SubscriptionEvent. Workspace creation itself still grants no
commercial access. Development enables this flow explicitly; production keeps
it disabled until commercial policy approves it.

- 2026-08-17: Workspace billing navigation now reverses only the canonical
  `workspace_subscriptions` routes with an explicit Workspace slug. The shared
  management account sidebar caused `/w/<slug>/settings/billing/plans/` to
  raise `NoReverseMatch` by reversing the ambiguous legacy `subscriptions`
  namespace without arguments. Desktop/mobile account navigation, main
  navigation, upgrade links, feature/subscription alerts, Workspace pages, and
  control-plane redirects now use slug-bearing billing routes or send global
  requests to the Workspace selector. A full plans-page shell render test
  protects the boundary.

- 2026-08-17: The global `/dashboard/` and legacy company-dashboard redirect no
  longer pass the retired `allow_profile_fallback` keyword to
  `resolve_request_workspace()`. They now honor the Phase 1 contract: explicit
  request Workspace context only, followed by active Membership-based routing
  to the Workspace selector. Regression tests cover both paths, and the source
  tree contains no remaining runtime use of the removed keyword.

- 2026-08-17: SaaS control-plane Phase 4 billing and entitlement normalization
  is complete. `Subscription.status` is the sole stored billing state;
  `is_active` and time-dependent status writes from `Subscription.save()` are
  removed. Effective trial expiry is derived without mutation, and valid
  commercial transitions run through a row-locked service that appends a
  `SubscriptionEvent`. Invoice capture and payment-failure provider paths use
  that service. Razorpay webhook identity is persisted with a provider-scoped
  uniqueness constraint, successful replays are acknowledged without repeated
  effects, and state changes plus processed evidence commit atomically. The
  entitlement API exposes typed `enabled()`, `require()`, and `limit()`
  decisions over registered namespaced codes. Missing, malformed, expired, or
  commercially unavailable grants fail closed; plan projection preserves
  explicit overrides, whose actor/reason provenance is database-enforced.
  Workspace seats, module gating, context processors, feature decorators, and
  subscription middleware consume the separated policies. Billing recovery
  remains reachable without changing Workspace identity, lifecycle,
  Membership/RBAC, or RLS. Migrations `subscriptions.0002` and `0003` are
  applied; Phase 5 has not started.

- 2026-08-17: SaaS control-plane Phase 3 Workspace operational lifecycle is
  complete. `Company.is_deleted` and the ordinary hard-delete setting/model/
  admin paths are retired. Migration `orgs.0003` maps archived rows and installs
  the independent `ACTIVE`, `SUSPENDED`, `ARCHIVED`, and `DELETION_PENDING`
  state model. A row-locked, reason-required, audited lifecycle service enforces
  the accepted transition graph and actor rules. Middleware enforces lifecycle
  after explicit Workspace resolution and independently of Membership, RBAC,
  Subscription state, and RLS; platform override bypasses Membership only, not
  inactive-Workspace boundaries. Recovery routes remain narrowly available to
  the authorized actors, inactive rows retain their Workspace ownership, and
  physical erasure remains reserved for a later privileged retention workflow.
  The migration applied normally. Verification passed 130 focused control-plane
  tests, all 12 restricted-role Party/Loans/Notify v2/Rates RLS tests, migration
  drift and system checks, and the foundation inventory with zero integrity
  findings and 95/95 forced-RLS coverage. Phase 4 billing normalization has not
  started.

- 2026-08-17: The local development database migration ledger is reconciled
  with the rebuilt baseline and Phase 2 is physically applied. The database
  retained old pre-baseline migration names while already containing the new
  baseline schema, causing `accounts.0002_initial` to try to recreate
  `accounts_userprofile.workspace_id`. Physical columns, constraints, 95
  forced-RLS tables/policies, and 42 Loans guard triggers were verified before
  marking only the equivalent rebuilt baseline migrations applied. The truly
  new `orgs.0002` then ran normally. Its migration is deliberately non-atomic
  at the migration level so PostgreSQL can commit reconciliation FK events
  before altering Membership constraints. The final plan has no pending
  migrations; foundation inventory reports zero integrity findings, zero null
  Membership roles, and correct Owner Memberships for all three Workspaces;
  `CompanyOwnership` is absent; forced RLS remains 95/95.

- 2026-08-17: SaaS control-plane Phase 2 ownership and authorization is
  complete. Migration `orgs.0002` reconciles every Workspace to
  `Company.owner_id`, creates/fixes its single mirrored Owner Membership,
  demotes competing Owner-role rows to Admin, fills null Membership roles,
  makes roles non-null, protects owner user deletion, and retires
  `CompanyOwnership`. `transfer_workspace_ownership()` locks the Workspace and
  affected Memberships, requires an existing target member and reason, updates
  the owner plus both roles atomically, rejects stale competing actors, and
  emits `OWNERSHIP_TRANSFER`. The request-independent `WorkspaceAccess` policy
  now supplies normalized namespaced actions, fail-closed `can()`/`require()`,
  and the sole superuser platform override. Secure middleware attaches it after
  Membership validation; control-plane view guards, decorators, and role policy
  consume it. Final Party/Loans/Notify v2/Rates helper convergence remains the
  explicitly planned Phase 9 boundary. Verification passed: 199 broad
  control-plane tests, 120 focused Phase 2/Orgs tests (including a real
  PostgreSQL competing-transfer test), and all 12 restricted-role RLS tests.
  Phase 3 is now complete as recorded above.

- 2026-08-17: SaaS control-plane Phase 1 (Workspace Resolution and Request
  Context) is complete. Workspace authority now comes only from a registered
  domain or a recognized Workspace-bearing path. Conflicting domain/path
  identities return HTTP 403 for every actor, including platform
  administrators. Global account, onboarding, selector, membership, profile,
  and account-settings routes explicitly clear request and PostgreSQL
  Workspace context. Profile Workspace remains a validated navigation
  preference only; request resolvers and context processors no longer use it
  or `request.tenant` as fallback authority. Middleware establishes
  `request.workspace`, its temporary identical `request.tenant` alias, and
  transaction-local RLS context before the separate subscription guard runs.
  Workspace billing has canonical `/w/<workspace-slug>/settings/billing/...`
  routes, and unscoped business roots including `/portal/` fail closed to the
  selector. No models, migrations, ownership/RBAC, lifecycle, entitlement
  semantics, or business-app architecture changed. The focused control-plane,
  tenancy, onboarding, subscription, route-map, and shell suites pass (164
  tests in the focused gate, plus all 12 restricted-role RLS tests). Phase 2
  has not started.

- 2026-08-17: SaaS control-plane Phase 0.5 architecture decision lock is
  complete. The normative contract is
  [docs/architecture/control-plane-contracts.md](architecture/control-plane-contracts.md).
  Five Accepted ADRs lock explicit domain/path Workspace authority and the
  `request.workspace`/RLS relationship; `Company.owner_id` with one mirrored
  Owner Membership; target `WorkspaceAccess` action authorization; a four-state
  operational lifecycle separate from Subscription billing state; and one
  fail-closed typed entitlement service. The contract also records canonical,
  transitional, deprecated, forbidden, and removal APIs; 25 invariants; a
  phase-by-phase impact map; and the exact Phase 1 middleware/resolver/context-
  processor/test boundary. The July tenant-billed subscription proposal is
  marked superseded by these accepted decisions while retaining Workspace-as-
  customer intent. This phase changed documentation only: no runtime model,
  migration, middleware, RBAC, billing, business-app, URL, or UI behavior was
  changed; its Phase 1 contract is now implemented as recorded above.

- 2026-08-17: The post-RLS SaaS control-plane audit is now the accepted
  incremental execution baseline under ADR
  `2026-08-17-saas-control-plane-audit-baseline.md`. Phase 0 closed the immediate
  security findings: profile detail/update are authenticated and self-only;
  profile Workspace choices expose only active memberships; persistent
  Workspace switch/select/clear/reset, member removal, and invitation revoke
  are POST-only; all shipped callers use CSRF-protected forms; and selection
  redirects accept only same-host `next` targets. Ten profile/method/template
  tests and 39 focused Workspace, invitation/team, and shell-render tests pass.
  The repository-based audit is at
  [docs/architecture/saas-control-plane-architecture-audit.md](architecture/saas-control-plane-architecture-audit.md).
  It preserves the request/RLS, component, onboarding, UI, and proposed lifecycle
  diagrams; capability and user-flow inventory; P0-P3 findings; security
  invariant matrix; duplication and django-tenants residue reports; proposed
  control-plane-to-data-plane contract; standards; and phased roadmap. This is
  an accepted baseline and roadmap; its Phase 0.5 decisions now live in the
  canonical control-plane contract. The remaining implementation risks are non-
  canonical ownership and broken/non-idempotent billing.
  All six architecture diagrams are also checked-in SVG assets generated from
  adjacent Graphviz sources, while expandable Mermaid source remains in the
  audit. The diagrams therefore render without Mermaid support.

- 2026-08-17: The active Workspace sidebar now renders exactly one Parties app
  link. The duplicate direct `party:party_list` entry was removed; the single
  canonical link uses the Workspace-slug Party route and retains active-state
  handling for both namespaced Party pages and the slug entrypoint.

- 2026-08-17: The Workspace dashboard no longer renders the retired DEA
  Dashboard/accounting quick action. The Workspace module registry now lists
  only surviving operational apps (Parties, Loans, Notify v2, and Rates) plus
  still-planned/platform capabilities; retired Accounting, DEA Operations,
  Inventory, Commodity, and DEA-backed Advanced Reporting entries are removed.
  Old accounting URLs remain HTTP 410 compatibility endpoints only and are not
  advertised by current UI.

- 2026-08-17: Workspace dashboard Party metrics now import `PawnLoanState`
  through the canonical Loans domain API rather than the persistence-model
  package. The stale nonexistent `DEFAULTED` lifecycle state was removed from
  the active-customer filter; current persisted candidates are APPROVED and
  ACTIVE. A focused selector regression test protects this cross-app boundary.

- 2026-08-17: Public account signup no longer crashes after authentication when
  no Workspace has been selected. The theme context processor now prefers
  `request.workspace`, safely tolerates `workspace`/legacy `tenant` being
  absent or `None`, and returns neutral public-theme defaults. Focused tests
  cover public authenticated requests, canonical Workspace context, and the
  temporary tenant alias fallback.

- 2026-08-17: A reusable end-to-end migration guide now documents how to move a
  Django SaaS project from schema-per-tenant storage to a shared PostgreSQL
  schema protected by forced RLS. It covers target invariants, inventory,
  direct ownership, transaction-local context, policy SQL, two-role database
  configuration, runtime conversion, bulk operations, migration-baseline
  rebuilding, package removal, production-vs-development cutovers,
  adversarial verification, rollback, failure modes, and completion criteria.

- 2026-08-17: Deterministic two-Workspace runtime smoke fixtures now exist via
  `seed_rls_smoke_workspaces`. The command is development-only, refuses an
  unsafe database role or incomplete RLS metadata, and idempotently creates two
  Workspaces with one Rates proof row each. Running it twice through
  `rokkad_runtime` passed: no context sees zero rows, each Workspace sees only
  its own row, and attempted cross-Workspace updates affect zero rows. The local
  fixtures are Workspace IDs 1 and 2 (`rls-smoke-one`, `rls-smoke-two`).

- 2026-08-17: Production-shaped runtime-role validation passes against the
  rebuilt local shared-schema database. The ordinary Django connection is
  `rokkad_runtime`: it is neither superuser nor `BYPASSRLS`, has no database or
  role creation privilege, and owns zero application tables. PostgreSQL reports
  all 95 surviving business tables with both RLS and FORCE RLS enabled. Without
  Workspace context, representative Party, Loans, Notify v2, and Rates queries
  each return zero rows. The current development database has no Workspace
  fixture, so positive scoped reads remain proven by the restricted-role RLS
  suites. `check --deploy` reports only the expected development-settings
  warnings for DEBUG, HSTS, SSL redirect, and the local secret key; deployment
  must use hardened production settings.

- 2026-08-17: Post-baseline retirement cleanup is complete. Eight historical
  phase/source-snapshot test files and the obsolete unimplemented Rates DRF API
  test were removed. Current suites pass independently: Loans 394, Party 74,
  Rates 14, control plane/accounts/onboarding/subscriptions/tenancy 153, and
  project/Notify v2/architecture/importing 142 (777 total). Cleanup uncovered
  and fixed active residue: Party merge/accounting UI references, undefined
  Notify settings database state, missing onboarding logging, dashboard links
  to retired Contact, an undefined dashboard Workspace variable, and 298 lines
  of dead lazy DEA forwarding handlers in Orgs. Old accounting/commodity/report
  bookmarks still resolve deterministically to HTTP 410 without importing DEA.
  Data import/export now derives its model registry from the four surviving
  shared-schema Workspace apps rather than the empty `TENANT_APPS` setting.

- 2026-08-17: The development-only migration history has been rebuilt from the
  surviving shared-schema model state. Recovery commit `319c399` preserves the
  complete pre-baseline state. The nine project apps now have 14 compact model
  migrations, followed by four explicit forced-RLS migrations and one Loans
  database-guard migration. A fresh isolated database
  `rokkad_baseline_rehearsal_20260817_no_tenants_no_acc` migrated successfully
  from zero with 95 canonical policies on 95 forced-RLS tables. The 38 current
  Loans PostgreSQL immutability/projection triggers are retained in one audited
  post-initial migration; transitional backfills, deleted-model operations,
  and retired accounting migrations are not part of the new baseline.
  `makemigrations --check`, Django system checks, the four restricted-role RLS
  tests, and all 394 Loans tests pass. Baseline testing also fixed three
  `bulk_create()` paths that bypassed automatic Workspace assignment. The
  repository-wide default suite still contains separate historical intent-test
  debt referring to retired DEA, Girvi, Product, Contact, and tenant-schema
  surfaces; those tests must be retired or rewritten, not used to restore the
  deleted architecture.

- 2026-08-17: The shared-schema Workspace/RLS tenancy ADR is accepted and its
  removal plan is active. A registry-derived correction finds 95 concrete
  models across Party, Loans, Notify v2, and Rates; 35 initially had direct
  Workspace ownership and 60 required conversion before the `django-tenants`
  backend could be safely removed. The earlier 90/37/53 inventory was stale.
  Phase 1 has started: `apps.tenancy` now provides the abstract direct-ownership
  model and transaction-local PostgreSQL `workspace_context`; its validation,
  database-setting, and conflicting-nested-context tests pass.
  Phase 2 control-plane conversion has started: Company and Domain are ordinary
  Django models, schema auto-create/drop behavior is removed, and migration
  `orgs.0025` removes the django-tenants schema validator while preserving the
  temporary routing column. Thirteen workspace lifecycle/invitation tests pass.
  Onboarding and control-plane creation no longer clone/provision schemas, and
  the Company post-save tenant seeding signal is removed. Fourteen focused
  lifecycle, invitation, and onboarding creation tests pass.
  SecureWorkspaceMiddleware now establishes transaction-scoped Workspace
  context without schema switching; Domain resolution uses the ordinary Domain
  model and public requests clear Workspace state. Twenty-five focused context
  and middleware tests pass.
  Party is the first surviving business aggregate converted to direct,
  non-null Workspace ownership. All ten Party models inherit the shared
  ownership contract; root identifiers and role keys are unique per Workspace,
  child and cross-Party relationships reject Workspace mismatches, and Party
  role seeding is explicitly Workspace-scoped. Transitional migrations
  `party.0006`-`0008` add, backfill, and enforce ownership. The backfill is a
  no-op only for an empty schema and fails closed for unowned rows without a
  tenant Workspace. Django checks, migration drift, and seven focused Party/
  tenancy tests pass.
  Rates is also converted: RateSource and Rate have direct ownership, Rate
  quotes are unique per Workspace, Rate rejects a source owned by another
  Workspace, form choices fail closed without context, and middleware/signal
  cache keys include the Workspace ID. Transitional migrations
  `rates.0003`-`0005` pass from an existing test database. Forty-one surviving
  concrete business models still required direct ownership at that checkpoint.
  Notify v2 is now converted across its entire eleven-model evidence graph.
  Ten previously schema-owned models gained direct Workspace ownership; the
  existing WhatsApp integration now uses the same context contract. Parent/
  child saves reject mixed Workspace chains, formerly global keys and provider
  identifiers are Workspace-scoped, webhook receipts no longer persist a
  tenant-schema label, and readiness, webhook, admin, and delivery runtime code
  no longer reads database schema state. Transitional migrations
  `notify_v2.0007`-`0010` apply cleanly. A subsequent registry check corrected
  the remaining Loans count from 31 to 38.
  All 38 formerly schema-owned Loans child/evidence models now inherit direct
  ownership; every one of Loans' 72 concrete models exposes a non-null
  Workspace field. Migrations `loans.0064`-`0066` add, backfill, and enforce
  the columns and apply successfully across the legacy test schemas. Loans'
  active schema-switching services and legacy tenant tests remain a separate
  runtime-conversion step; direct ownership alone does not complete RLS safety.
  The shared-schema settings cutover is now active: Party, Loans, Rates, and
  Notify v2 are in `SHARED_APPS`, `TENANT_APPS` is empty, Django uses the
  standard PostgreSQL backend with no tenant router, ordinary file/static/cache
  and logging configuration replaces django-tenants helpers, and the obsolete
  tenant-aware test runner is deleted. The four remaining Loans production
  services no longer use `schema_context`; their audit writes remain inside the
  caller's ordinary transaction and Workspace context. A new WorkspaceTestCase
  replaces TenantTestCase for the first four converted service suites, and all
  38 tests pass from a freshly created standard shared-schema test database.
  Remaining django-tenants imports are compatibility/test/command cleanup and
  must be removed before deleting the dependency.
  Production Python now has no direct `django_tenants` import. Request
  Workspace resolution uses `request.workspace`; Party portal audits use the
  grant's direct Workspace owner; subscription middleware and Orgs views no
  longer ask django-tenants for a public-schema name; Company admin no longer
  inherits TenantAdminMixin. Workspace seeding uses `--workspace-id` plus
  `workspace_context`, global permission seeding is ordinary, and the obsolete
  schema-parity command is deleted. Seventeen focused context/access tests pass.
  The package remains temporarily because legacy tests and historical migration
  imports still reference it; those are the next removal boundary.
  The django-tenants dependency declaration is now removed. Historical
  migration `orgs.0008` no longer imports its schema validator, the unused
  legacy settings module is deleted, and Party/Loans TenantTestCase and
  TenantClient imports are converted to WorkspaceTestCase/WorkspaceClient.
  Sixteen focused Orgs/Party tests pass on a fresh standard database. The two
  specialized Loans concurrency suites now use per-connection Workspace
  context and both pass. Their conversion exposed and fixed a shared-schema
  write defect: FundingPledgeItem bulk creation now sets Workspace ownership
  explicitly. Twenty-nine route/architecture intent tests also pass, Django
  checks report no issues, migration state has no drift, and project Python and
  requirements contain no django-tenants dependency/import. PostgreSQL RLS is
  now proven on the Rates aggregate through migration `rates.0006`. The
  reusable migration operation enables and forces the canonical
  `workspace_isolation` policy with matching `USING` and `WITH CHECK`
  predicates. Nine focused context/RLS tests pass under an actual temporary
  `NOSUPERUSER NOBYPASSRLS` role, proving missing-context denial, scoped ORM
  and raw-SQL reads, scoped update/delete, and rejection of cross-Workspace
  bulk inserts. At that proof checkpoint, Rates was the only protected
  aggregate. The authoritative registry and system checks now
  account for all 95 surviving models and validate direct non-null ownership;
  database checks compare the active rollout registry to PostgreSQL RLS/FORCE
  and policy metadata. A deploy-only check rejects superuser, BYPASSRLS, and
  table-owner runtime connections. The owner/runtime role contract and grant
  procedure are documented in `docs/implementation/postgresql-runtime-role.md`.
  Party is the second protected aggregate: migration `party.0009` enables and
  forces the policy on all ten Party tables, and restricted-role tests prove
  no-context denial, cross-Workspace read isolation, and rejection of spoofed
  bulk inserts. Ten focused registry/RLS tests pass. Production runtime-role
  creation remains a deployment operation and was not executed locally.
  Notify v2 is now the third protected aggregate: migration `notify_v2.0011`
  enables and forces the canonical policy on all eleven notification/provider
  evidence tables. Restricted-role tests prove missing-context denial,
  cross-Workspace event-type reads, and rejection of spoofed bulk inserts.
  This checkpoint covers 23 of 95 surviving models, and all 12 focused
  registry/RLS tests pass without migration drift. Loans migration
  `0067` completes the policy rollout across its 72 root, child, and evidence
  tables through the reusable app-state operation. SQL inspection confirms
  exactly 72 `ENABLE ROW LEVEL SECURITY` statements. The active registry and
  PostgreSQL metadata gate now cover all 95 surviving business models.
  Restricted-role Loans tests prove missing-context denial for both License and
  Series rows, Workspace-scoped reads, and rejection of a spoofed cross-
  Workspace child bulk insert. All 14 focused registry/RLS tests pass. Code and
  migrations are RLS-complete; creating the permanent runtime role and using it
  for deployed web/worker connections remains an external deployment step.
  Applying the policies to the existing `fresh_clean` development database was
  intentionally stopped by the fail-closed migration because that database
  records historical Loans migrations as applied while the corresponding
  public-schema tables (for example `loans_collateralappraisal`) do not exist.
  The RLS migration transaction rolled back and all four RLS migrations remain
  unapplied locally. Fresh test databases create all 95 tables and pass the
  complete metadata gate, so the code path is sound; the existing database is
  legacy-schema state and now requires the planned clean development database
  rebuild rather than skipped policies or fake migrations.
  A new non-destructive development database, `rokkad_shared_dev`, has now
  replaced `fresh_clean` in development settings; the old database remains
  untouched. Ordinary Django migrations built the new database successfully
  from zero, including all four RLS migrations. The database metadata check
  passes and PostgreSQL reports exactly 95 `workspace_isolation` policies on 95
  tables with both RLS and FORCE RLS enabled. The remaining operational step is
  to provision a password-managed restricted runtime login and use it for web/
  worker connections while retaining the current owner only for migrations.
  That local role split is now complete. `rokkad_runtime` is a LOGIN role with
  `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`, owns no
  application tables, and has only schema/table/sequence DML grants plus owner-
  established default privileges. Default development connections now use
  `DB_RUNTIME_USER`/`DB_RUNTIME_PASSWORD`; Django confirms the active user is
  `rokkad_runtime` with superuser and BYPASSRLS both false, and the tenancy
  deployment check passes. Owner-only `migration` and `test` settings isolate
  schema changes and disposable test-database creation from web/worker
  settings. Four focused registry/Loans RLS tests pass through the new test
  settings. Production must supply distinct runtime and migration secrets.
  The final django-tenants cleanup is complete: the wheel is uninstalled from
  `.venv314`, a whole-runtime scan finds no package import, mixin, router,
  schema-context, schema-switch, or `migrate_schemas` reference, and the
  Workspace test helper no longer installs no-op connection methods. The last
  missed imports in `accounts.views` and the dormant Cloudflare storage helper
  are removed; clearing Workspace selection now stores `None` rather than
  looking up a synthetic public-schema Company. README and AGENTS migration
  guidance now describe shared-schema RLS and ordinary owner-only migrations.
  Twenty-nine focused control-plane, Party, Loans, and registry tests pass with
  the package absent. A broader mixed 51-test run exposed six pre-existing stale
  configuration/invitation intent expectations tied to retired Girvi or older
  routes; these are test-debt failures, not django-tenants imports.

- 2026-08-17: Product, Savings Scheme, and tenant Terms are unregistered and
  physically removed with their migrations and Product templates. Product
  setup, navigation, seed operations, and direct route mount are retired; old
  workspace inventory bookmarks return HTTP 410. The public legal Terms of
  Service page remains. The surviving tenant business apps are Party, Loans,
  Notify v2, and Rates.

- 2026-08-17: DEA and tenant/Standalone Accounting are physically removed,
  including their migrations, commands, tests, and dedicated templates. Both
  apps and their top-level URL mounts are unregistered. Party accounting
  mappings, accounting navigation/setup/seeding, and Product's obsolete
  journal-entry FK plus DEA migration dependency are removed. Old workspace
  accounting/commodity/report bookmarks return HTTP 410 pending the tenancy
  URL-baseline rebuild. Django checks, migration drift, and all 15 accounting
  retirement boundary tests pass.
  Empty-database rehearsal then exposed and fixed a Product SQL projection that
  still selected the retired journal FK. The project suite now completes its
  migration setup; its first remaining failure is an unrelated stale invitation
  intent assertion expecting direct `Membership.objects.get_or_create` usage.

- 2026-08-17: Accounting-era cutover code and tests are retired. The PawnLoan
  cutover selector and command are deleted. Party portal invoices now return an
  explicit empty unsupported summary, portal payments use only `PawnLoanEvent`,
  and Party merge no longer imports DEA mappings. Party, Loans, Notify v2, and
  Rates current runtime have no DEA, tenant-Accounting, or Standalone-Accounting
  imports. Twenty-eight focused Loans tests, compilation, Django checks, and
  migration-drift checks pass; Party merge tests passed before the legacy
  multi-tenant suite exceeded its setup timeout.

- 2026-08-17: Remaining risk/exposure/report accounting vocabulary is removed.
  `cash_receivable_basis` and `OVERDUE_INTERPRETATION_VARIANCE` now describe the
  actual Loans concepts. Report bundles and exports no longer carry delivery
  status or empty posting-event state; report/runbook UI now presents operational
  integrity and contains no DEA retry procedure. Thirty-three focused risk,
  report, export, and boundary tests pass.

- 2026-08-17: Loans accounting-delivery readiness is removed rather than kept
  as an always-successful compatibility layer. Balance objects no longer expose
  posting readiness/blockers; release and portfolio selectors no longer branch
  on them; reversal preflight has no accounting mode; dead reconciliation UI
  and accounting-labelled event/document copy are removed. Forty-six focused
  balance, release, report, document, and boundary tests pass.

- 2026-08-17: Loans has no current DEA dependency or DEA-shaped compatibility
  contract. Stale DEA queue messages, the unused report inspector parameter,
  voucher/journal test fixtures, document outboxes, and integration-mode test
  preferences are removed. Thirty focused report/document/boundary tests pass.
  DEA names remain only in historical Loans migrations and explicit retirement
  guards pending the clean development migration baseline. Generic accounting
  labels and always-ready posting fields remain the next terminology cleanup.

- 2026-08-17: The now-constant interest-recognition concept is fully removed
  from current Loans code and schema. Migration `loans.0063` drops it from
  economic policies and disbursal snapshots; domain contracts, balances,
  lifecycle payloads, setup forms, and tests no longer expose accounting
  recognition. Operational accrual rows and compound capitalization remain.
  Migration application, 13 focused policy/balance tests, Django checks,
  migration-drift checks, source guards, and diff validation pass. The broader
  tenant suite reached eight passing tests before its two-minute setup limit.

- 2026-08-16: The always-ready accounting-readiness compatibility API is fully
  deleted. No PawnLoan lifecycle service imports or calls it, package exports
  are removed, its dedicated compatibility tests are deleted, and a boundary
  guard prevents restoration. Lifecycle services retain their own operational
  validation. Thirty-seven focused tests, compilation, Django checks, migration
  drift, and diff validation pass. `accounting_recognition` remains temporarily
  Interest recognition is now cash-only. Operational monthly accrual rows and
  contractual compound capitalization remain Loans-owned economic behavior,
  not accounting-app dependencies.

- 2026-08-16: All nine current Loans relationships named `accounting_event`
  are now `loan_event`: disbursal snapshot, interest accrual, three allocation/
  principal line models, release and release reversal, auction and auction
  reversal. Migrations `0060` and `0061` preserve existing data through field
  renames and refresh ordering/uniqueness state. Both migrations applied cleanly;
  36 focused tests and the highest-risk auction completion/reversal tenant test
  pass. The full pawn service module exceeded the two-minute setup limit without
  reporting a test failure.

- 2026-08-16: The auction operational coverage gap is closed. A real tenant
  integration test now proves sent Notify v2 notice evidence, auction start,
  exact recovery, immutable recovery allocation, loan closure, collateral
  disposal, auction reversal, exact compensating allocation, custody restoration,
  and loan reopening without DEA/outbox assertions. The test passes. Remaining
  Phase 4 work has neutralized persisted `accounting_event` field names and
  compatibility readiness terminology without changing stored evidence.

- 2026-08-16: Loans-only renewal and auction integration coverage is restored
  without accounting. Renewal verifies request-key idempotency, one renewal,
  source settlement-event ownership, successor opening-event ownership,
  successor activation, and the expected principal carry-forward. Auction
  verifies overdue eligibility, Notify v2 notice-job evidence, request-key
  idempotency, single-auction persistence, and reasoned cancellation. Both real
  tenant tests pass. Auction completion/reversal remains a narrower follow-up.

- 2026-08-16: Remaining executable Loans UI tests no longer import or create
  deleted `PawnLoanAccountingEvent`/outbox models. Report, statement, PDF, and
  workspace-isolation fixtures now use `PawnLoanEvent`; three setup-console
  tests dedicated solely to outbox failure listing/retry were removed. Real
  Notify v2 notice delivery coverage remains. Direct converted UI execution
  reached four scenarios with one stale display assertion before the expensive
  multi-schema run timed out; that assertion was removed because Party statement
  evidence intentionally shows event/correction state, not delivery state.

- 2026-08-16: The uncollectible 2,300-line accounting-era disbursal integration
  suite is retired; it depended directly on deleted outbox types and DEA voucher/
  journal models. Operational disbursal, accrual, repayment allocation, reversal,
  and release evidence remains covered by the passing pawn-draft service suite;
  replacement renewal/auction integration coverage is tracked as an explicit
  gap. Notice fixtures now use `PawnLoanEvent`, document fixtures no longer fake
  outboxes, and configurable document contracts replace accounting delivery/
  reference bindings with Loans-owned event/document evidence. Nine document
  tests pass.

- 2026-08-16: Accounting delivery-handler compatibility is removed from every
  PawnLoan financial lifecycle API and from immutable event recording. Real
  Notify v2 notice-delivery handlers remain unchanged. The operational pawn
  draft/economics suite was converted to event-only calls and all 28 focused
  draft/boundary tests pass while retaining allocation, reversal, release, and
  immutability assertions. The monolithic accounting-era disbursal test module
  remains the next major conversion target.

- 2026-08-16: Phase 4 legacy event-module shims are removed. Immutable event
  recording now lives directly in `services/event_recording.py`, frozen event
  payloads live in `integrations/event_payloads.py`, and their internal public
  types use `LoanEvent*` terminology. The deleted `accounting_outbox.py` and
  `dea_payloads.py` paths are guarded by boundary tests. Thirty-one focused
  tests, Django checks, migration-drift checks, compilation, and diff validation
  pass. Mixed accounting-era lifecycle tests remain the next conversion slice.

- 2026-08-16: Loans Phase 4 now exposes the event spine through neutral runtime
  names: `PawnLoan.loan_events`, `record_loan_event`, `event_recording`, and
  `event_payloads`. Migration `0059_rename_loan_event_relations` updates the
  reverse relations without replacing event data. Four obsolete DEA/voucher
  report tests were removed while operational report coverage was retained;
  29 focused tests, Django checks, migration-drift checks, and diff validation
  pass. The old implementation filenames remain temporary internal shims.

- 2026-08-16: All Loans runtime imports, annotations, queries, documents, and
  obligation relations now use `PawnLoanEvent`; the temporary
  `PawnLoanAccountingEvent` alias/export is removed. Historical migrations and
  mixed stale tests are the only remaining old-name references. Twenty-six
  focused boundary/registration/readiness/balance/cutover tests pass.

- 2026-08-16: Phase 4 began by renaming the preserved model from
  `PawnLoanAccountingEvent` to canonical `PawnLoanEvent`. Migration
  `0058_rename_pawnloanaccountingevent_pawnloanevent` applied successfully and
  preserves the existing table data through Django's model rename operation.
  Event recording and obligation model references use the neutral identity;
  a temporary Python alias keeps mixed call sites working. Twenty-three focused
  tests, Django checks, migration-drift checks, and diff validation pass.

- 2026-08-16: Dead DEA voucher/journal inspection and accounting-delivery issue
  classification are removed from Loans reports. The two pure DEA contract/
  readiness test modules are deleted; operational portfolio, daily activity,
  correction, custody, duplicate-event, and renewal report coverage remains.
  Eleven focused operational report/boundary tests pass. Mixed historical
  lifecycle/UI tests still need accounting assertions removed rather than
  wholesale deletion.

- 2026-08-16: `PawnLoanAccountingOutbox` is removed from current Loans models
  and migration `0057_retire_accounting_outbox` drops its index and table. The
  obsolete delivery-status enum and dedicated outbox service test are deleted,
  all runtime ORM prefetch/select paths were detached from the relation, and
  the migration applied successfully to the retained test database. Twenty-two
  focused tests, Django checks, and migration-drift checks pass.

- 2026-08-16: Lifecycle result objects for disbursal, repayment, accrual,
  capitalization, release, auction, renewal, and reversal no longer expose
  outbox fields. Delivery diagnostics, retry controls, delivery messages, and
  DEA references are removed from Loans web and document surfaces. Balances
  ignore retired delivery state unconditionally. Thirty-five lifecycle/
  boundary tests and the final 21-test focused suite pass; Django checks and
  diff validation pass. The dormant model is ready for schema removal.

- 2026-08-16: Loans lifecycle event recording no longer creates accounting
  outbox rows, schedules delivery, invokes handlers, or supports retry. The
  retry service and URL are removed. Existing lifecycle result shapes receive
  a non-persistent `RECORDED` compatibility value while their outbox fields are
  removed incrementally. Twenty focused retirement/readiness/balance/cutover
  tests and Django checks pass.

- 2026-08-16: Accounting-retirement Phase 3 has removed every direct runtime
  Loans-to-DEA import. The DEA delivery adapter and receivable reconciliation
  selector are deleted; operational reports no longer call DEA or expose
  posting health, DEA references, or delivery state. Cutover readiness now
  checks Loans migrations, numbering, and operational acknowledgements only.
  The standalone Django check and eight focused boundary/cutover tests pass.
  The temporary outbox model/write path remains for the next schema-safe slice.

- 2026-08-16: Accounting-retirement Phase 2 removed the accounting integration
  mode and its operational/cutover setup blocker. Normal Loans balances and
  financial actions no longer fail because an accounting delivery is pending;
  automatic outbox delivery is disabled unless an explicit handler is supplied.
  The focused boundary, readiness, balance, and cutover suite passes all 19
  tests. Delivery/reconciliation compatibility state remains for Phase 3.

- 2026-08-16: Accounting-retirement Phase 2 has removed external accounting as
  a loan-action gate. The temporary readiness API is now an always-ready,
  DEA-free compatibility wrapper; no period, ledger, or account mapping can
  block disbursal, repayment, accrual, capitalization, release, renewal, or
  auction workflows. Borrower-account setup service, route, view, template,
  exports, and UI messaging are removed. Fourteen focused boundary/readiness/
  balance tests pass, and direct Loans runtime DEA imports fell from six files
  to four delivery/reconciliation/reporting targets.

- 2026-08-16: Accounting-retirement Phase 1 evidence classification is
  documented. The Loans accounting-event model is confirmed as the current
  canonical economic event spine and will be preserved before neutral renaming;
  its DEA outbox is delivery-only retirement state. New boundary tests freeze
  the six-file direct DEA import surface and confirm target runtime apps have no
  direct Standalone Accounting imports.

- 2026-08-16: On branch `no-tenants-no-acc`, accounting retirement is now an
  accepted product decision. The constitution and ADR explicitly narrow Rokkad
  to an operational lending system with immutable Loans-owned evidence and no
  vouchers, journals, ledgers, or financial statements. Phase 1 is active:
  preserve and characterize the current Loans event spine before removing DEA
  delivery, readiness, reconciliation, and accounting terminology.

- 2026-08-16: Party-native test-fixture conversion has started. Fixed sale,
  fixed purchase, unfixed sale, and unfixed purchase DEA service suites no
  longer import or construct Contact customers; they use Party directly and
  create DEA accounts through `Account.party`. A combined tenant test run
  advanced through ten tests without a failure but exceeded the five-minute
  command timeout during the expensive multi-schema run. Sixteen real stale
  test modules remain (plus one Orgs negative source assertion that intentionally
  names the retired import).

- 2026-08-16: The uninstalled Contact package is physically deleted. Django
  startup and migration-drift checks pass without it. Project-owned
  `/contact/...` redirects remain live, and the Girvi/Contact route-intent suite
  passes all 24 tests after correcting its stale exact-prefix inventory for the
  existing Loans, portal, and Accounting routes. Remaining retirement cleanup
  includes converting surviving historical test fixtures that still import
  `contact.Customer` to Party-native fixtures.
  The clean rehearsal database contains zero Contact/Girvi/legacy-Notify
  ContentTypes and zero associated permissions in both public and tenant
  schemas.

- 2026-08-16: The replacement development migration history is Contact-free.
  Notify v2, Product, and DEA now create Party-owned state directly while
  retaining later migration node names and indispensable custom operations.
  Contact has been removed from active and legacy settings. Django system
  checks pass and the full project reports no migration drift.

- 2026-08-16: Guarded database
  `rokkad_baseline_rehearsal_20260816_contactfree` migrated successfully from
  empty for `public` and tenant `contactfree_tenant`. Every DEA migration,
  Product view/constraint migration, Loans database guard, and Notify v2
  migration completed without Contact installed. The migration plan contains
  no Contact app, and no surviving app migration depends on Contact.

- 2026-08-16: Isolated reference database
  `rokkad_baseline_rehearsal_20260816` migrated successfully from empty for
  `public` and tenant `baseline_tenant` using guarded rehearsal settings. The
  tenant reference has 193 base tables, 5 views, 63 user triggers, and 2,880
  constraints; public has 48 tables and 435 constraints. It creates six Contact
  tables, zero Girvi/legacy-Notify tables, and the expected Notify v2 tables.

- 2026-08-16: Phase 7 migration-baseline cutover is active and protected by a
  verified PostgreSQL custom archive at
  `.local-backups/fresh_clean-pre-contact-baseline-20260816-154116.dump`
  (8,833,038 bytes; 17,671 TOC entries). The audit found indispensable custom
  operations across surviving apps, so mechanical migration regeneration is
  rejected. The baseline must preserve current SQL views, database guards,
  masters/seeds, repairs, and lifecycle constraints while omitting retired-app
  transformations.

- 2026-08-16: Contact's supported web surface is retired. `/contact/...`
  bookmarks now resolve through project-owned `legacy_contact_urls` and redirect
  to the Party list; tenant URLs no longer import Contact's URLConf or views.
  Contact is now uninstalled after the development migration-baseline rewrite.
  Fifteen of
  sixteen route-intent tests pass; the remaining failure is the known stale
  prefix expectation omitting existing portal/loans/accounting routes.

- 2026-08-16: DEA invoices are now schema-level Party-only. Migration
  `dea.0048` removes `SalesInvoiceVoucher.customer` and
  `PurchaseInvoiceVoucher.vendor` plus their obsolete indexes. Model save and
  posting account resolution no longer fall back through Contact; required
  Party ownership selects the customer/supplier subledger. All six focused
  resolver/posting tests pass, both new migrations execute successfully in the
  test database, and model drift/Django/compilation/diff checks pass.

- 2026-08-16: DEA `Account.contact` is removed from runtime and schema state.
  Required `Account.party` is now the sole counterparty identity; migration
  `dea.0047` drops the legacy FK, the account manager and examples are
  Party-only, and the focused unbridged-Party account test passes. Migration
  graph/state checks, Django checks, compilation, and diff checks pass. The two
  nullable invoice evidence FKs remain the next Contact schema boundary.

- 2026-08-16: The Contact customer bridge is fully retired. Its service,
  backfill command, dedicated tests, and Party-merge Customer conflict/transfer
  behavior are removed. DEA account creation/save/balance lookup is Party-only,
  and Party export no longer publishes `legacy_customer_id`. Remaining
  retirement migrations fail closed with direct Party-mapping guidance rather
  than referencing the deleted command. The focused unbridged DEA account test,
  Django checks, compilation, and diff checks pass.

- 2026-08-16: The user-facing legacy Customer-to-Party conversion workflow is
  retired: route, view, Contact-backed form, list action, template, and web tests
  are removed. `customer_bridge` now has no production runtime caller; it is
  retained only behind the explicit `backfill_parties_from_customers` migration
  command until Contact data removal. The focused route/template test and
  Django checks pass. The broad canonicalization suite still has its unrelated
  stale Girvi-route expectations.

- 2026-08-16: Party read surfaces no longer depend on Contact compatibility.
  Portal invoices filter solely by required `SalesInvoiceVoucher.party`, and
  the regression passes with no legacy Customer. Party detail removed its dead
  Girvi-era `legacy_customer` activity adapter and now derives loan counts from
  the Loans-owned Party history selector. The portal regression passed; the
  second UI test timed out while preparing its separate tenant schema.

- 2026-08-16: Loans borrower-accounting setup is now Party-native. It creates
  or reuses DEA's `BORROWER / BORROWER_LOAN_RECEIVABLE` mapping directly from
  the PawnLoan borrower and no longer imports the Contact customer bridge,
  creates a compatibility Customer, or emits Customer fields in its result and
  audit evidence. The focused Loans regression passed; the combined two-test
  command later timed out during the DEA test after one passing test.

- 2026-08-16: Orgs dashboard composition and global navigation are now
  Contact-free. Party owns the customer dashboard summary through active
  CUSTOMER roles, Party creation years/types, and Party-linked active
  PawnLoans. Desktop navigation opens Parties instead of legacy Contacts.
  Nine focused tests, compilation, Django checks, and diff checks pass.

- 2026-08-16: Girvi is physically retired. Its installed-app entry, 136-route
  URLConf, source package, migrations, templates, graph artifacts, root
  validation scripts, and generated bytecode are removed. `/girvi/...`
  bookmarks now redirect through `django_project.legacy_girvi_urls` to the
  canonical PawnLoan list. Global navigation and Contact loan metrics now use
  Loans/Party-owned data. Django checks, the Loans migration graph, and eight
  focused retirement tests pass. Historical route-intent and renamed Girvi-only
  fixture bodies remain test-cleanup debt; they no longer load the retired app.

- 2026-08-16: Legacy `notify` is fully removed from installed apps and source:
  models, migrations, views, services, templates, tests, assets, and the obsolete
  shared `utils/loan_pdf.py` helper are deleted. Temporary `/notify/...`
  bookmark names now live in `django_project.legacy_notify_urls` and redirect
  safely to Notify v2 without translating legacy IDs. Notify v2 migration and
  Django checks pass. The selected authorization suite has two unrelated stale
  failures because its expected middleware-prefix set omits the existing
  `accounting/` route.

- 2026-08-16: Girvi runtime no longer imports legacy Notify or reads its generic
  notification relations. Dashboard/detail/operational presentation now reports
  no Girvi notice state, facade notice counts are zero, and the stale
  `one_year_reminder` task fails safe with an explicit disabled result. Loans
  and Notify v2 notice workflows are unchanged. Eight focused tests, compile,
  Django, and diff checks pass.

- 2026-08-16: Tenant default seeding no longer imports, schedules, or exposes a
  skip flag for legacy Notify. Notify v2 remains the only notification seed
  action and currently owns no global defaults. The legacy seed method bodies
  have been physically deleted. Dry-run/help checks and Django system checks
  pass.

- 2026-08-16: Legacy Notify URLs and Orgs notification aliases no longer invoke
  legacy views. Existing route names/bookmarks redirect to the Notify v2 batch
  list, deliberately discarding incompatible legacy object IDs, and remaining
  legacy menu links now open Notify v2. Legacy models stay installed until
  Girvi and tenant-default seeding dependencies are removed. Six focused tests,
  Django checks, and diff checks pass.

- 2026-08-16: Orgs workspace loan compatibility routes now dispatch to Loans
  PawnLoan views while retaining their public route names. The loan module and
  chooser no longer advertise Girvi, and workspace numbering now opens Loans
  license/series setup. Focused route-intent tests and Django checks pass.

- 2026-08-16: DEA period close no longer imports or mutates Girvi. The Girvi
  unreleased-loan warning and automatic period-close accrual catch-up are
  removed. DEA still enforces its own draft-voucher and balance-sheet fatal
  checks plus depreciation/prepaid warnings and the existing reconciliation
  placeholder. No Loans replacement was added because Loans has no approved
  period-close batch accrual command. The focused boundary test, Django checks,
  and DEA drift check pass; static runtime search finds no Girvi import in DEA.

- 2026-08-16: The Orgs workspace dashboard no longer imports the Girvi facade.
  `get_workspace_pawn_loan_dashboard_summary` now supplies active count, total
  due, outstanding interest, lifecycle counts, and closed-progress from
  workspace-scoped PawnLoans and canonical balance selectors. The old Girvi
  "sunken" metric is deliberately empty because Loans has no authoritative
  equivalent. Two focused selector/composition tests, Django checks, and drift
  checks pass. Orgs still contains explicit Girvi deep-route compatibility
  wrappers; those are a separate route retirement boundary.

- 2026-08-16: Party portal payment discovery no longer imports Girvi. Sales-
  invoice receipts remain sourced from DEA `PaymentVoucher`; PawnLoan repayments
  are sourced from immutable Loans accounting events scoped through
  `loan.borrower`, excluding reversed events. Portal amounts use frozen
  principal, interest, and fee components plus the event currency. Three focused
  Party/Loans selector tests, Django checks, and migration-drift checks pass.
  Static runtime search finds no Girvi import anywhere in the Party app.

- 2026-08-16: Party detail and customer-portal loan summaries now read canonical
  `Loans.PawnLoan` rows through `get_party_pawn_loan_history_summary`; neither
  imports the Girvi facade. Active financial amounts come from the canonical
  Loans balance selector, while draft/approved rows intentionally expose no
  posted outstanding amount. Two focused selector tests, Django checks, and
  Loans/Party drift checks pass. The existing database-backed portal test could
  not run because the stale `test_fresh_clean` database already exists; it was
  not deleted automatically. Portal payment lookup still has a Girvi source
  branch and is the next Party boundary.

- 2026-08-16: The Girvi-to-Notify-v2 producer integration is retired. Single-
  loan and bulk reminder routes/actions are removed, Girvi auction transitions
  no longer create notification batches, and Notify v2's Girvi batch service
  and PDF renderer are deleted. Generic Notify v2 event emission, delivery,
  providers, artifacts, downloads, and historical batch evidence remain. Twelve
  focused generic Notify v2/access tests, Django checks, and model-drift checks
  pass. No database rows were deleted.

- 2026-08-16: Notify v2's active batch UI is now domain-neutral. It no longer
  links to Girvi or legacy Notify, no longer exposes the Girvi-only "Print All"
  renderer route, and tenant default seeding no longer installs Girvi reminder
  event/policy/template rows. Historical batches, artifacts, digital dispatch,
  downloads, and printed/posted evidence remain readable. The focused batch UI
  test, Django checks, and migration-drift checks pass. Girvi producers and the
  dormant Girvi renderer/service are intentionally left for the next coordinated
  deletion slice so current Girvi imports are not broken mid-step.

- 2026-08-16: Notify v2 now owns its workspace authorization boundary and no
  longer imports decorators from retiring legacy `notify`. The permission
  contract remains unchanged (`data_view` for view/print, `data_edit` for
  edit/send, and Owner/Admin for provider setup). Four focused fail-closed
  access tests and `manage.py check` pass. Girvi-specific Notify v2 rendering
  and batch producers remain the next dependency boundary; legacy Notify is
  not yet removable.

- 2026-08-16: DEA sales and purchase invoices now require Party for new writes,
  forms, admin, search, display, reporting, account resolution, and version-3
  posting fingerprints. Legacy Customer/vendor FKs are nullable `SET_NULL`
  evidence only. Fail-closed migration `dea.0046` protects unmapped historical
  invoices. DEA migrations `0044` through `0046`, including the Party balance
  SQL view, executed successfully in the test database; all six focused
  sales/purchase posting tests pass. A direct numeric balance-view test exceeded
  120 seconds during tenant setup and returned no assertion result. No production
  database was migrated.

- 2026-08-16: DEA's unmanaged `account_balances` projection and dashboard
  consumers now use Party rather than Contact. Reversible migration `dea.0045`
  recreates the view from `dea_account.party_id` and records Party in migration
  state. System, compilation, graph, and drift checks pass. Plain `sqlmigrate`
  is a no-op under the tenant router, but the migration has since executed
  successfully through the tenant test runner. Numeric view reconciliation
  remains a fresh-database gate. No production database was migrated.

- 2026-08-16: DEA Account now has required Party ownership with a temporary
  nullable Contact evidence link. `dea.0044` performs a fail-closed Party
  backfill. New Party account resolution no longer requires a legacy Customer;
  account forms, filters, primary account/aging/period/opening-balance surfaces,
  and commodity event consistency checks use Party. Django checks, compilation,
  migration graph, and drift checks pass. The focused tenant database test did
  not finish within 180 seconds and returned no assertion result. Unmanaged DEA
  balance views still expose Contact and remain a recorded blocker. No production
  database was migrated.

- 2026-08-16: Phase 1 retirement execution has removed two concrete Contact
  dependencies. Product price overrides now belong to Party end-to-end, with a
  fail-closed `product.0015` backfill. Notify v2 recipients no longer store a
  Contact FK; `notify_v2.0006` protects mapped legacy associations while keeping
  Party optional for generic/system recipients. Django checks and migration
  drift checks pass, both migrations applied in the focused test database, and
  the targeted Notify v2 batch test passes. The Product suite was not completed:
  stale `--keepdb` tenant rows caused uniqueness failures and a clean test-DB
  rebuild exceeded 180 seconds. No production database was migrated.

- 2026-08-16: The Contact/Girvi/legacy-Notify retirement ADR is accepted and
  Phase 0 is complete. `manage.py check` passes with zero issues. The inventory
  records Contact FKs in DEA, Product, Party, and Notify v2; Notify v2's legacy
  Notify authorization dependency; Girvi consumers across DEA, Party, Orgs,
  onboarding, configuration, and Notify v2; and the surviving migration nodes
  that prevent package-first deletion. Loans already owns the FundingLoan
  target. Notify v2's 29-test baseline has 21 passes and eight pre-existing
  access-decorator errors; the Party suite exceeded the 120-second baseline
  window. No runtime behavior, schema, settings, route, or database data changed.

- 2026-08-16: A documentation-only proposed ADR and gated execution plan now
  define retirement of `contact`, `girvi`, and legacy `notify`, while retaining
  `party`, `loans`, `notify_v2`, and DEA. The plan orders Party replacement,
  Girvi consumer removal, Notify v2 cleanup, legacy Notify retirement, DEA
  decoupling, physical package deletion, and a clean development migration
  baseline/database rebuild. It includes per-phase verification and rollback
  gates. No runtime code, model, migration, settings, route, data, or database
  behavior changed; implementation remains gated on acceptance of the proposed
  ADR and explicit resolution of development-data and TakenLoan/funding
  dispositions.

- 2026-08-14: The `no-tenants` seed and database-role baseline is complete.
  Tenant defaults resolve to DEA core/voucher types, Terms and Rates fixtures,
  Product reference rows, Party roles, legacy Notify templates, and Notify v2
  Girvi defaults; public defaults resolve to permission setup. The current
  development database uses the `postgres` superuser and Docker trust auth, with
  no migration/runtime role split, so restricted-role RLS proof is a critical
  Phase 1 gate. Historical dumps and older Product fixtures still need an owner
  KEEP/ARCHIVE/DELETE disposition. Documentation only.

- 2026-08-14: The `no-tenants` Phase 0 integrity inventory is complete. The live
  tenant model graph contains 252 uniqueness rules, 358 tenant foreign-key
  edges, 28 cross-app edges, 10 generic relation surfaces, and three unmanaged
  accounting/inventory balance views. The inventory defines Workspace-scoped
  uniqueness, composite same-Workspace constraints, generic-link safeguards,
  view security, index policy, and per-app completion gates. Documentation only;
  runtime implementation remains gated on the proposed ADR.

- 2026-08-14: The `no-tenants` Phase 0 registry/coupling inventory is recorded.
  Django currently registers 212 tenant-app models: only 35 have a direct
  non-null Workspace FK and 177 lack direct ownership. 76 discovered test modules
  directly use tenant test helpers, and 35 migration files containing raw SQL
  objects require clean-baseline review. This remains analysis-only pending ADR
  acceptance; no runtime or database behavior changed.

- 2026-08-14: The `no-tenants` branch now has a proposed architecture decision
  and phased execution plan for replacing `django-tenants` schema isolation
  with direct Workspace ownership, restricted-role PostgreSQL RLS, explicit
  transaction-scoped context, tenant-aware relational integrity, and a clean
  development migration baseline. The earlier hybrid/schema-tenancy targets are
  marked as historical pending acceptance of the replacement ADR. This is a
  documentation-only planning slice; no runtime code, model, migration,
  dependency, settings, or database behavior changed.

- 2026-08-14: Workspace invitation acceptance now requires the authenticated
  account to have a verified allauth `EmailAddress` matching the invited email.
  The check is service-owned in `control_plane.accept_invitation`, so direct
  invite links and the invitations dashboard share it; mismatched or unverified
  identities cannot create membership or mark the invitation accepted. General
  signup and ordinary tenant access remain optional-verification. The full orgs
  gate passes 115 tests. No model or migration changed.

- 2026-08-14: SaaS foundation Phase 0A/0B is complete without runtime or
  schema changes. Eight new characterization/inventory tests pass, and the
  read-only `check_saas_foundation` public-schema inventory reports zero owner,
  membership-role, ownership-history, invitation-shadow, or Guardian data
  findings across six non-public workspaces and eight memberships. All Role
  rows currently have zero Django permissions, so hard-coded RBAC remains the
  real authority and cannot yet be removed. A broader 53-test SaaS gate has 49
  passes and exposes four pre-existing baseline failures: `/accounting/` is
  missing from middleware workspace-required prefixes, and three intent tests
  are stale relative to current invitation-service/routes. Details are in
  `docs/implementation/saas-foundation-phase0-baseline.md`.

- 2026-08-14: The proposed canonical MVP SaaS architecture is documented in
  `docs/architecture/SAAS_TARGET_ARCHITECTURE.md` for review before any
  implementation. It keeps the Django monolith and `django-tenants`, assigns
  every foundation-audit finding a FIX/SIMPLIFY/DELETE/KEEP/DEFER/REJECT
  disposition, and deliberately rejects a provisioning state machine,
  membership suspension lifecycle, generic subscription access-mode engine,
  public email-job subsystem, enterprise billing roles, and append-only audit
  framework for MVP. No runtime code, migrations, or data changed.

- 2026-08-14: A documentation-only deep SaaS foundation audit is complete in
  `docs/implementation/saas-foundation-architecture-audit.md`. It consolidates
  current identity, schema tenancy, workspace lifecycle, membership/RBAC,
  invitations, subscriptions/entitlements, audit, jobs, data lifecycle, and
  testing evidence into a launch-focused scorecard, readiness matrix, target
  architecture, and phased remediation plan. No runtime code or migrations
  changed. The P0 recommendation is to harden schema deletion, verified email,
  authoritative tenant resolution, provisioning/lifecycle, ownership,
  subscription recovery boundaries, and background tenant context before
  production.

- 2026-08-14: The future legacy Notify retirement plan is now dependency-first.
  Every consumer will receive an owned boundary and move off direct legacy
  imports before `notify` is isolated as read-only history. A dependency gate,
  authorization decoupling, and read-only inventory come first. Runtime and
  table removal remain blocked on zero writes, parity, tenant reconciliation,
  retention, and upgrade safety.

- 2026-08-14: Legacy `notify` retirement is documented as future staged work.
  Notify v2 remains the target, but immediate deletion is prohibited while
  Girvi producers, printing, Party reporting, tenant seeds, routes, shared
  authorization, and historical evidence depend on legacy models. The plan
  starts with access decoupling and a read-only tenant inventory, and requires
  parity, reconciliation, retention, and upgrade-safety gates before removal.

- 2026-08-14: Fixed `/data-tools/import/` app discovery for tenant apps declared
  with explicit AppConfig class paths such as `loans.apps.LoansConfig` and
  `accounting.apps.AccountingConfig`. Import/export now resolves installed
  AppConfig labels and canonical module paths instead of mistaking class names
  for Django app labels.

- 2026-08-13: Fixed the workspace Party detail crash caused by Girvi loan
  history counting the removed `GivenLoan.notifications` reverse relation.
  Notice totals now use one explicit batch query through the canonical generic
  `notify.NotificationItem` link. The exact failing `jcl1` Party 5 history now
  resolves successfully without restoring the obsolete coupling.

- 2026-08-13: The next workspace WhatsApp Cloud slice is documented for future
  implementation. It will verify Meta identity, preview and send one controlled
  approved-template test, reconcile an authenticated callback, retain immutable
  acceptance evidence, and invalidate readiness after credential changes.
  Saving/enabling credentials remains insufficient for operational acceptance;
  no runtime behavior was added in this documentation slice.

- 2026-08-13: Meta WhatsApp Cloud credentials are now workspace-owned rather
  than global Django settings. Owner/Admin has a write-only tenant setup form;
  access token, verify token, and app secret are Fernet-encrypted using the
  deployment `WORKSPACE_SECRET_ENCRYPTION_KEY`. Dispatch, readiness, GET webhook
  verification, POST HMAC verification, and callback phone-ID matching resolve
  only the active tenant's enabled integration, with no global fallback. Tenant
  migration `notify_v2.0005` is required.

- 2026-08-13: PawnLoan risk borrower communication now has one KISS,
  tenant-scoped manual policy per workspace. Owner/Admin can choose the initial
  email/WhatsApp channel, optional quiet hours, a same-kind/channel borrower
  cooldown, and an internal DPD escalation threshold. Readiness and confirmation
  enforce quiet hours and cooldown; policy changes invalidate previews and the
  confirmed values are frozen as notice evidence. Escalation is guidance only;
  automation, fallback, bulk sending, and automatic borrower contact remain
  disabled. Tenant migration `loans.0056` is required.

- 2026-08-13: Owner/Admin can now manage Party-specific PawnLoan service-notice
  consent for email, SMS, and WhatsApp. Each channel records Allow, Block, or
  Opt out, mandatory evidence/reason, actor, and timestamp. The blocked risk
  notice page links directly to consent and Party contact correction. This is
  service-notice consent only, not a marketing-consent framework.

- 2026-08-13: The manual email-first risk borrower-notice flow is implemented
  for eligible DPD and maturity alerts. Owner/Admin sees exact recipient,
  template/version, financial basis, subject, and body before confirmation; the
  service revalidates under lock, creates one source-linked immutable notice,
  and queues its Notify job. Blocked readiness creates no intent.

- 2026-08-13: PawnLoan risk communication readiness is implemented without a
  send action. The tenant-scoped decision boundary revalidates open/current
  DPD or maturity risk, Party contact, explicit per-channel service consent,
  active Notify template/version, real provider readiness, and duplicate intent.
  `PawnLoanNotice` now has nullable risk alert/event and template evidence plus
  event/kind/channel/template-version uniqueness. LTV and assessment failures
  remain ineligible. Notify digital stub fallback cannot mark delivery sent
  outside explicit Django debug mode. Tenant migration `loans.0055` is required.

- 2026-08-13: The proposed PawnLoan risk-alert borrower-communication flow now
  includes a detailed end-to-end illustration: DPD transition example, current
  state revalidation, channel/consent/provider eligibility, exact preview and
  template evidence, immutable notice creation, Notify v2 delivery ownership,
  retry semantics, risk resolution distinction, and a future configured flow.
  This remains documentation-only pending the recorded readiness gate.

- 2026-08-13: The proposed PawnLoan risk-alert-to-borrower workflow is documented
  in `docs/flows/pawn-risk-alert-borrower-communication.md`. Notify v2 receives a
  conditional-go assessment for a manual approved pilot, but automatic
  configurable multi-channel delivery is blocked on enforced consent/opt-out,
  fail-closed real-provider readiness, source/template evidence, dedupe, and
  WhatsApp callback security/tenant routing. No communication runtime changed.

- 2026-08-13: Material immutable `LoanRiskEvent` transitions now project into
  risk-specific internal work items shown on the Risk Portfolio. Worsening DPD,
  LTV breach/critical, maturity attention, and assessment failure create one
  open alert per loan/category; current snapshot state resolves recovered work.
  Alerts do not send customer or staff email and do not reuse the outbound
  `LoanOperationalNotice` delivery-intent model.

- 2026-08-13: The in-app PawnLoan Operations Runbook now documents the canonical
  tenant-aware scheduled risk invocation, daily timing, batch draining,
  selected/current/error meanings, non-zero failure monitoring, safe reruns,
  and operator verification. The detailed operations runbook carries the same
  deployment guidance and distinguishes manual refresh as a recovery action.

- 2026-08-13: The existing bounded `reassess_pawn_loans` command is now ready
  for scheduler monitoring: it reports selected/current/error counts and exits
  unsuccessfully when any assessment fails, while the service retains visible
  `ERROR` snapshots. The PawnLoan Operations Console now shows active and
  unassessed loan counts plus the latest successful risk-assessment timestamp.

- 2026-08-13: PawnLoan fee-ledger readiness now uses DEA's canonical ledger-key
  resolver, matching the posting rules. An existing `Service Income` ledger is
  therefore accepted as the supported alias for `DOCUMENT_CHARGE_INCOME`; when
  neither identity exists, readiness still fails closed with the actionable fee
  ledger blocker. All five PawnLoan posting rules now use that same resolver for
  disbursal, repayment, interest, release, and renewal, eliminating the
  readiness/posting mismatch.

- 2026-08-13: The Loans web-boundary consolidation audit is complete. Four dead
  legacy action helpers and eight obsolete imports were removed after the
  FundingLoan/PawnLoan extractions. Remaining mutations in `loans.views` are
  cohesive setup/document administration, mixed verification worklist/detail
  POSTs, expired-draft setup transfer, outbox retry, and risk refresh; they are
  not being split merely to minimize file size. Focused modules retain URL
  compatibility exports, and the current organization satisfies the KISS rule.
  The broader 30-test PawnLoan UI run exposed and led to correction of one
  shared draft-readiness wiring regression. Its stale navigation assertion was
  replaced with the intended contract: authorized operators see PawnLoans,
  while Loans Setup remains Owner/Admin-only; `/internal/` is naming, not an
  authorization boundary. The complete 30-test tenant-backed PawnLoan UI module
  now passes.

- 2026-08-13: The KISS PawnLoan recovery split is complete without a generic
  recovery framework. Auction lifecycle actions live in
  `loans.web.pawn_auction_actions`; release-and-renew preview/completion and
  renewal reversal live in `loans.web.pawn_renewal_actions`. Auction and renewal
  PDFs remain in document delivery. The tenant-backed renewal contract passes,
  and existing action URLs remain compatible through `loans.views` exports.

- 2026-08-13: Two further KISS PawnLoan HTTP slices are complete. Standalone
  storage creation/transfer and verification completion/resolution/alert actions
  now live in `loans.web.pawn_custody_actions`; verification start and observation
  intentionally remain in their combined worklist/detail coordinators. Customer
  notice creation and delivery retry now live in `loans.web.pawn_notice_actions`.
  Three tenant-backed custody regressions and the notice command regression pass;
  existing URLs remain compatible through `loans.views` exports.

- 2026-08-13: The KISS PawnLoan release HTTP slice is complete. Full release
  quote/confirmation and the explicit unsupported partial-release response now
  live in `loans.web.pawn_release_actions`; release posting and custody mutation
  remain service-owned, while document delivery stays separate. Existing URLs
  remain compatible through `loans.views` exports.

- 2026-08-13: The KISS PawnLoan financial HTTP action split is complete.
  Disbursal/readiness, borrower accounting setup, repayment preview/recording,
  accrual finalization, capitalization, and financial-event reversal now live
  in `loans.web.pawn_financial_actions`. Posting and transaction rules remain in
  existing services and DEA boundaries; `loans.views` preserves URL-compatible
  exports. Four tenant-backed disbursal, setup, repayment, accrual, and reversal
  regressions pass.

- 2026-08-13: The first KISS PawnLoan HTTP action split is complete. Draft
  create/edit, economic preview, collateral split, draft photograph capture,
  approval, reopen, and cancellation now live with their direct form-mapping
  helpers in `loans.web.pawn_draft_actions`. Existing services retain domain and
  transaction ownership, and `loans.views` compatibility exports preserve all
  URL names. Five tenant-backed origination, split, preview, and lifecycle
  regressions pass; Django checks pass.

- 2026-08-13: The FundingLoan HTTP split is complete. Console/detail rendering
  and immutable document delivery live in `loans.web.funding`; ordinary Django
  mutation adapters live in `loans.web.funding_actions`. Existing services still
  own all business rules and transactions, while `loans.views` compatibility
  re-exports preserve every URL name and callable import. The
  five tenant-backed Funding UI cases pass; the broader 33-test Funding run
  exceeded the four-minute harness window after those five passes with no
  reported failure. Django checks and diff hygiene pass.

- 2026-08-13: The second physical Loans view-module split is implemented.
  Read-only operations console, risk portfolio, customer-notice ledger, and
  operations runbook coordinators now live in `loans.web.operations` and are
  compatibility re-exported by `loans.views`. Risk refresh and outbox retry
  mutations intentionally remain in the legacy module because tests and callers
  patch their service seams there. Three tenant-backed console, filtering,
  pagination, and authorization regressions pass, including explicit risk-page
  authorization; Django checks, Loans migration drift, compatibility exports,
  and diff hygiene are clean.

- 2026-08-13: The first physical Loans view-module split is implemented.
  Read-only portfolio reports, section exports, and Party statements now live
  in `loans.web.reports`; `loans.views` re-exports the same callables so URL
  names and route behavior remain unchanged. The module retains identical
  tenant decoration, Party scoping, date parsing, export errors, filenames, and
  administrator context. Five export-contract tests and two tenant-backed
  report/Party-statement regressions pass; Django checks, Loans migration drift,
  and diff hygiene are clean.

- 2026-08-13: The document-issuance views thinning slice is complete. Official
  issue reuse, layout/print-profile resolution, configurable rendering,
  fixed/legacy recovery auditing, and immutable issue persistence now live in
  one application service. Views retain permission checks and HTTP response
  handling, and both compatibility paths remain supported. The initial
  75-test document batch exceeded three minutes after 12 passing tests with no
  reported failure; the narrowed gate passes three orchestration invariants and
  two tenant-backed official issue/reprint/schema-v3/recovery regressions.

- 2026-08-13: The third Loans views/forms thinning slice is complete. PawnLoan
  draft create/update and form-supplied photographs now cross one service-owned
  boundary. Uploads are validated before number allocation or mutation, the
  service maps evidence to retained and newly created collateral identities,
  database writes remain atomic, and newly stored files are cleaned up if a
  later media write fails. Four focused service invariants and two complete
  tenant-backed create/edit/add/remove UI regressions pass; final project checks
  pass; Django checks, Loans migration drift, and diff hygiene are clean.

- 2026-08-13: The second Loans views/forms thinning slice is implemented.
  PawnLoan economic setup now calls one atomic service command for the economic
  calculation policy and its Gold/Silver rate policies instead of coordinating
  three writes in the view. Shared scope/effective dates are explicit, and a
  failure in either rate leaves no partial policy set. Eight focused economic
  policy tests and the tenant-backed setup POST regression pass; Django checks,
  Loans migration drift, and diff hygiene are clean.

- 2026-08-13: The first Loans views/forms thinning slice is complete. Series
  create/update views no longer own the multi-write transaction. New service
  commands atomically coordinate Series identity/active state with the required
  PawnLoan and release sequences, preserve consumed counters during formatting
  changes, and roll back the entire update if either sequence is invalid. Nine
  focused license/series service tests and the tenant-backed setup-page
  regression pass; Django checks, Loans migration drift, and diff hygiene are
  clean.

- 2026-08-13: Loans notice-delivery orchestration is consolidated. Customer
  `PawnLoanNotice` and internal `LoanOperationalNotice` remain distinct intent
  aggregates, while one shared coordinator now owns schedule enforcement,
  linked Notify-state handling, idempotent SENT/cancelled behavior,
  deterministic queued selection, batch bounds, and delivery counts. Business
  eligibility, recipient/source snapshots, and idempotency remain in their
  respective services; Notify v2 remains the provider-evidence authority. Two
  coordinator invariants and all eight tenant-backed notice workflow tests
  pass; Django checks, Loans migration drift, and diff hygiene are clean.

- 2026-08-13: The PawnLoan balance -> obligation -> exposure contract is
  formalized. A canonical obligation-state selector now owns active schedule
  resolution and the allocation fold for remaining, due, overdue, and unpaid
  DPD rows. Exposure and delinquency both consume it instead of independently
  traversing obligations. Exposure reports contractual-versus-recorded principal
  variance while keeping recorded event balance and projected interest distinct.
  Fourteen focused obligation/risk and transactional exposure tests pass,
  including cash-accrual and repayment-schedule regression coverage.

- 2026-08-13: Risk monitoring hardening is implemented. Owner/Admin can refresh
  one active PawnLoan or a bounded batch of up to 50 missing/stale/error
  assessments from the snapshot-backed operations portfolio; HTMX and ordinary
  POST use the same service boundary. Members are forbidden before service
  execution, foreign/non-active identifiers fail closed, and batch selection
  retains `select_for_update(skip_locked=True)`. Snapshots now persist source
  provenance for the calculation contract, monitoring/collateral policy,
  collateral items, approved appraisals, and applicable valuation rates. Source
  fingerprinting is narrowed to approved appraisals, applicable policy scope,
  and relevant INR/24K metal rates. Seven orchestration/invariant tests and three
  focused HTTP/permission tests pass; Django checks, migration drift, and diff
  checks are clean. Tenant migration `loans.0053` adds snapshot provenance and
  has been applied through `migrate_schemas` to all local tenant schemas.

- 2026-08-13: Pawn collateral appraisal authority cleanup is implemented.
  Draft `latest_appraised_value` remains editable proposal input; approval now
  appends immutable, loan-date-effective appraisal evidence and reapproval
  creates a superseding version. Disbursal no longer creates appraisals, and
  post-approval collateral valuation/release no longer falls back to the draft
  field. Risk invalidation now limits monitoring-policy changes to their
  effective scope and valuation-rate changes to applicable INR/24K metal and
  snapshot dates; irrelevant rate changes do not stale the portfolio. Django
  checks, migration drift, `git diff --check`, 10 focused release/risk tests,
  and the database-backed approval-to-release valuation regression pass. The
  combined lifecycle/disbursal suite exceeds the current four-minute command
  window because its tenant fixture repeatedly rebuilds the complete schema;
  its focused release boundary passes after the corrections.

- 2026-08-13: Accepted the loan-application boundary ADR. FundingLoan is now
  explicitly supported; disabled-prototype declarations and assertions were
  removed. Girvi and PawnLoan now have independent navigation and origination;
  the workspace `loan__new_module_enabled` preference, cutover settings screen,
  conditional context/routing, and feature-gate tests were removed. The generic
  workspace Loans route presents an explicit application chooser. Snapshot-backed
  PawnLoan risk portfolio monitoring is available from the operations console.
  Schema-v1/v2 and explicit legacy print-profile recovery remain supported and
  now have a documented removal gate. Django checks, Loans migration-drift,
  26 focused domain/readiness/risk tests, and all 28 Loans setup UI tests pass.

## Latest Update

- Girvi Operations Console now links to the registered global `rate_list` URL
  instead of the nonexistent `rates` namespace, preventing its setup-health
  panel from raising `NoReverseMatch`.

- Workspace Preferences now redirects correctly after saving a section. The
  view returns Django's reversed URL string directly instead of treating it as
  an object with a `.url` attribute, so changing Accounting integration mode
  between `DEFERRED` and `DEA` no longer raises an `AttributeError`.

- Workspace lifecycle is now visible and truthful. Owner-only Workspace
  Settings exposes a Danger Zone archive action requiring exact-name
  confirmation; archive preserves the tenant schema and all business evidence,
  removes the workspace from active selection, and clears the actor's stale
  active-workspace pointer. A global archived-workspaces screen allows only the
  original Owner or platform administrator to restore the same schema. Normal
  UI never invokes permanent `hard_delete`. The archive view authorizes against
  the workspace ID in the URL rather than the public/previous `request.tenant`,
  so a legitimate Owner is not rejected before target-aware checks run. The
  shared Owner guard also accepts its documented platform-admin override instead
  of rejecting the `Superuser` role label. Ten focused lifecycle tests and all
  104 existing orgs tests pass; no migration is required.

- Loans reports no longer crash when reconciling posted DEA references. The
  DEA facade's inspection return path was restored from unreachable code, and
  Loans now categorizes an unexpected null adapter result as
  `DEA_INSPECTION_UNAVAILABLE` rather than dereferencing it.

- Collateral monitoring continues to fetch Gold/Silver valuation rates only
  through the Rates facade. Disbursal now promotes approved origination item
  values into immutable `CollateralAppraisal` evidence; loans created during
  the pre-fix gap retain an explicit compatibility read from the documented
  legacy item value, so lower-of valuation no longer becomes unknown solely
  because that appraisal row was absent.

- PawnLoan risk assessment now gets contractual maturity from the active
  repayment schedule, with the existing balance-derived maturity as legacy
  compatibility. Risk fingerprinting and portfolio maturity filters no longer
  assume a nonexistent `PawnLoan.due_date` database field.

- Loans Setup now exposes explicit immutable monitoring-policy configuration
  for workspace defaults or license overrides. PawnLoan risk warnings link
  administrators directly to it; no compliance thresholds are silently
  invented when configuration is absent.

- PawnLoan detail valuation no longer reads the nonexistent reverse-relation
  attribute `PawnLoan.policy_snapshot_id`; compliance provenance now uses the
  actual `LoanPolicySnapshot.pk`. Detail projections also degrade to visible
  diagnostic errors instead of HTTP 500 for legacy/incomplete active loans
  lacking a policy snapshot.

- PawnLoan draft submission now defaults to Save when the operator presses
  Enter; Preview remains an explicit secondary action. Invalid submissions
  show and focus a prominent "draft was not saved" summary while retaining
  the existing field-specific loan and collateral errors.

- Loan product catalog operations are implemented under Loans Setup. Owner/Admin
  can idempotently seed the four standard drafts, review every contractual
  term, activate one version per product, retire it from new origination, and
  create the next immutable draft from active terms. Activation/retirement are
  audited, existing loans retain their version, and migration `0047` enforces
  one active version per product.

- Loan product migration portability was corrected after the first
  `migrate_schemas` acceptance run: the product-version readiness index now
  uses the <=30-character name `loans_product_ready_idx` in current model
  state. Historical migration `0039` remains immutable; migration `0048`
  safely renames the old index and also tolerates development schemas that
  already contain the corrected name. No business data is changed.

- Loan architecture Phase 11 implementation is ready for acceptance. Migration
  `0046` registers immutable Key Facts/repayment-schedule issues; loan detail
  exposes due, DPD, exposure, collateral, LTV, flags, severity, explanations,
  and read-only Loans/DEA receivable variance. Existing workflow authority is
  deliberately unchanged. Four-product browser/document/accounting
  walkthroughs, parity review, and Owner acceptance remain before declaring
  the architecture complete. Migrations through `0048` were applied to all
  seven configured development schemas on 2026-08-12; a follow-up migration
  plan reported no pending Loans operations.

- Loan architecture Phase 10 application work is complete. The explicit-
  tenant `reassess_pawn_loans` command claims bounded batches with
  `skip_locked`, source commits invalidate affected snapshots, and daily dates
  capture time-only transitions. Portfolio selectors now filter and paginate
  typed risk projections and aggregate exposure by severity/product in SQL;
  stale and error rows remain visible. Pilot-scale timings remain a deployment
  measurement.

- Loan architecture Phase 9 is complete. Migration `0045` adds immutable,
  deduplicated risk-transition evidence. Snapshot publication now appends
  explainable maturity, delinquency, LTV, valuation, performance, severity,
  policy, assessment-error, and recovery events in the same transaction while
  repeated rebuilds produce no duplicate history.

- Loan architecture Phase 8 is complete. Migration `0044` adds a unique typed
  current-risk projection per workspace/loan. Refresh and rebuild services
  expose stale/error diagnostics, remain idempotent, and compare comprehensive
  source fingerprints under lock before publishing calculated assessments.
  The projection is explicitly rebuildable and cannot authorize workflows.

- Loan architecture Phase 7 is complete. Migration `0043` adds immutable,
  effective-dated workspace monitoring policies with optional license
  overrides and overlap protection. Pure risk assessment now produces
  explainable maturity, DPD, valuation, LTV, performance, severity, action,
  policy identity, and deterministic fingerprint results without workflow or
  accounting side effects.

- Loan architecture Phase 6 valuation foundation is complete. Migration `0042`
  adds immutable effective-dated collateral appraisals and preserves legacy
  appraised values as labelled backfill evidence. The new read-only valuation
  selector resolves historical rates/appraisals and eligible custody, while a
  pure LTV result separates policy breach, headroom, unknown evidence, and full
  economic shortfall using the Phase 4 exposure basis.

- Loan architecture Phase 5 is complete. Obligation-derived delinquency now
  distinguishes due-today from overdue, derives DPD from the oldest unpaid due
  date, keeps three-day operational grace separate from regulatory DPD, and
  reports variance against the unchanged legacy maturity-overdue rule.

- Loan architecture Phase 4 is complete. `get_pawn_loan_exposure()` now
  separates recorded event-fold balances, unfinalized actual-outstanding
  interest, obligation-based due/overdue amounts, accounting receivable,
  maturity payoff, total economic exposure, and product-aware LTV basis. The
  projection segments periods at effective repayment dates and frozen tranche
  balances, fixing the legacy period-opening behavior without rewriting
  finalized evidence. Loan detail explicitly labels recorded versus projected
  values and warns that projections are neither finalized nor posted.

- Loan architecture Phase 3 is complete. Extra principal on an installment now
  appends a new schedule version using the unchanged EMI (or unchanged equal-
  principal component), shortening tenure and regenerating only the remaining
  contract. Prior schedules and allocations stay immutable. Reversing the
  prepayment terminates the replacement and automatically restores the earlier
  schedule as active. Allocation row locks, event/order uniqueness, idempotent
  request keys, and the reconciliation fold close the concurrency and integrity
  boundary for persisted obligations. Migrations `0040` and `0041` provide the
  tenant-scoped obligation ledger and append-only termination/reactivation
  evidence. Disbursal, repayment, release, renewal, auction, and reversal paths
  participate without moving posting ownership away from DEA.

- Loan architecture Phase 2 is complete. A pure, versioned repayment schedule
  engine now generates single-payment bullet, periodic-interest bullet,
  flexible partial-payment, EMI, and equal-principal schedules. It supports
  mixed collateral rates, original-day month-end recovery, explicit rounding
  residue, zero-rate installments, exact principal reconciliation, and stable
  fingerprints. Previewing performs no loan, outbox, DEA voucher, or journal
  write; persisted obligations remain Phase 3 work.

- Loan architecture Phase 1 is complete. Workspace-owned `LoanProduct` and
  immutable `LoanProductVersion` foundations now represent repayment structure,
  amortisation, frequency, tenor bounds, operational grace, extra-payment rule,
  availability, status, and calculation-contract version. An idempotent tenant
  command seeds the four accepted products as drafts so they cannot become
  lending policy merely by running the command. New drafts require an active,
  in-date, tenor-compatible version; edits and renewals preserve it. Migration
  `0039` labels historical loans with a retired legacy/unspecified version and
  then enforces a non-null product contract on every PawnLoan.

- Loan Products, Exposure, and Risk Phase 0 is complete. The new conformance
  baseline inventories current contracts, event-folded balances, repayment
  allocation, accounting ownership, and tenant boundaries. Golden tests now
  make two important behaviors explicit: maturity becomes overdue the next day
  without moving for operational grace, while the legacy interest engine keeps
  a period-opening principal base after a mid-period repayment. The latter is
  recorded as a required calculation-contract change for new RBI-aligned
  contracts. Four-product schedule fixtures, workspace-scoped selector/command
  regressions, and event-to-DEA reconciliation complete the gate; no runtime
  behavior or schema changed in Phase 0.

- The Owner accepted the Loan Products, Obligations, Exposure, and Risk
  architecture with RBI-aligned gold-loan defaults. Canonical ADR
  `docs/adr/2026-08-11-loans-product-obligation-and-risk-architecture.md`
  records the decision. The execution roadmap now defines Phases 0-11 with
  explicit invariants, models/migrations, service changes, tests, dependencies,
  exclusions, and acceptance gates. Implementation has not started.

- The Loan Exposure, Risk Assessment, and Portfolio Monitoring blueprint is now
  organized under `docs/architecture/loan-risk/`. The full canonical plan is
  preserved, while focused concept documents, proposed decision briefs, a
  phased roadmap, and a review-status page make it digestible. The old plan
  path remains as a compatibility pointer. Implementation stays blocked until
  the Owner reviews its open business decisions.

- PawnLoan interest internals now have a durable implementation reference at
  `docs/implementation/pawn-loan-interest-calculation.md`, covering frozen
  tranche/policy evidence, calendar periods, slab fractions, opening-period
  principal bases, item rounding, advance-interest consumption, finalization,
  recognition, repayment, capitalization, release catch-up, event-folded
  balances, overdue semantics, and the recorded-versus-projected exposure gap.

- Future PawnLoan appraisal and collateral-risk work is now explicitly scoped
  in `docs/plans/pawn-collateral-risk-and-appraisal.md`. It separates contractual
  maturity overdue from LTV margin breach and full market-value shortfall,
  proposes a non-writing current-exposure projection plus rate/appraisal
  valuation, and records the unresolved authority and performance decisions.

- PawnLoan collateral photographs now render as secured thumbnails on both the
  draft-correction form and loan detail. Thumbnail requests reuse the
  tenant-scoped media endpoint in inline mode; clicking still downloads the
  original immutable evidence, and appending a new capture never replaces an
  earlier photograph.

- PawnLoan borrower selection now uses the shared Party autocomplete instead
  of rendering every active Party in a plain dropdown. Operators can search by
  name, party code, phone, relation name, or email; results and submitted
  values remain restricted to active tenant Parties, and create/edit
  preselection behavior is preserved.

- PawnLoan draft create/edit now asks for one searchable Series selection
  instead of independent License and Series values. The Series label includes
  its owning license, the server derives that license for policy and regulatory
  evidence, and the model/service consistency guards remain in force.

- Loans usability UP2.4 is complete, closing the primary UP2 scope. A new
  Owner/Admin customer-notice ledger provides 50-row pages and composable
  loan/recipient, notice-kind, channel, Notify delivery-state, and scheduled-
  date filters; missing delivery jobs remain explicit evidence. The operations
  console replaces its capped failed-only table with all tenant accounting
  outbox rows filtered by loan/key/error, status, event kind, and effective
  date. Retry remains available only for failed rows. Loans still reaches
  Notify state through its integration adapter, and neither worklist mutates
  notice, outbox, DEA, or delivery evidence.

- Loans usability UP2.3 is complete. Owner-only collateral-storage and
  physical-verification worklists now use deterministic 50-row pages. Storage
  filters cover code/name/path, descendant-aware hierarchy, level, and active
  state; verification filters cover session/scope/operator, hierarchy, status,
  and inclusive start dates. Per-row collateral and expectation counts were
  replaced with query annotations. Custody and verification evidence remains
  unchanged.

- Loans usability UP2.2 is complete. The Owner/Admin issued-document evidence
  ledger no longer silently truncates at the newest 200 rows: every immutable
  issue is reachable through 50-row pages. Search plus document type, issue
  kind, profile source, and inclusive issued-date filters compose and survive
  pagination. Historical issues without LPD7 profile provenance have an
  explicit filter, and opening an issue still serves its exact stored PDF.

- Loans usability UP2.1 is complete. The primary PawnLoan worklist now applies
  tenant scope before a dedicated `django-filter` FilterSet, supports combined
  text/state/license/Series/inclusive-date filtering, and paginates at 25 rows
  while preserving active query parameters. License and Series choices are
  workspace-bound. Issued-document, storage/verification, and notice/
  diagnostic worklists remain in the ordered UP2 follow-up.

- Loans usability follow-up UP1 is complete. Draft/edit, post-draft collateral
  append, and release-and-renew additional collateral now support direct mobile
  rear-camera intent and an in-page desktop webcam capture dialog. Captured
  JPEGs still pass through the existing server-side media validation and
  immutable hash evidence. The active usability plan records bounded
  django-filter/Paginator tables as UP2 and canonical workspace Loans URLs as
  ADR-gated UP3; the audit confirms current `/w/<slug>/loans`,
  `/loans/internal`, and `/loans/setup` planes are inconsistent and some slug
  detail/report aliases still delegate directly to Girvi.

- P12 was accepted by the workspace Owner on 2026-08-10; all twelve Loans
  capability scenarios are accepted. LPD7.4 is complete. New configurable
  loan-ticket issues now resolve `Series -> Workspace -> built-in` physical
  profiles and package independently rendered Original/Terms/Duplicate/D3
  surfaces as A5 sequential or A4 side-by-side output. Pair validation rejects
  missing mandatory front evidence, missing back surfaces, dishonest
  actual-size combinations, and multi-page side-by-side surfaces. Existing
  official issues are returned from their exact stored bytes before current
  layout/profile resolution, so later assignment changes cannot alter or break
  historical reprints. Owner/Admin retains audited
  `?print_profile=legacy` compatibility recovery; there is no silent fallback.
  Issue evidence records built-in/workspace/Series/legacy source and immutable
  profile identity. Diagnostics now validate each Series' effective
  layout/profile pair. Forty-four renderer/contract tests plus the effective-
  pair integrity test and configured issue-route test pass; system checks are
  clean and `jcl1` still has zero findings. Owner/Admin can now create, edit,
  clone, publish, assign, preview/test-print, and retire versioned print
  profiles under Loans setup. Assignment fails before mutation when an
  effective logical layout cannot supply the requested physical composition.
  The issued-documents ledger exposes immutable provenance and serves the
  exact stored artifact. No migration was required. The real physical printer
  matrix is the only remaining LPD7 acceptance gate. The in-app document
  printing guide now describes the LPD7 layout/profile boundary, both
  resolution orders, preview/test-print workflow, immutable issue evidence,
  and explicit audited recovery paths.
  New layout creation now emits logical-surface schema v3: physical
  `copy_mode` and `sheet` composition are rejected, visual authoring exposes
  only logical page/surface settings, and schema-v3 loan tickets require an
  explicit resolved print profile. Advanced JSON cannot downgrade a new draft.
  Existing schema-v1/v2 revisions and audited legacy recovery remain intact.

- P12's accepted boundary rejects Members
  before administrator-only auction/correction identifiers are looked up and
  rejects Members and Admins before Owner-only storage/physical-verification
  identifiers are looked up. The explicit platform-superuser override is
  consistent across these views and their services. Foreign-workspace loan,
  document, photo, scan, Party, and license sources return the same 404 as an
  unknown identifier. The focused role and isolation tests plus the complete
  nine-test collateral media/storage/verification gate pass.

- P11's accepted report hub exposes CSV, XLSX, and PDF
  for every required projection plus direct license-register, available ticket,
  repayment-receipt, release-memo/Form H, renewal-agreement, and Party-statement
  navigation. Daily and Party histories expose event, delivery, original/
  compensation linkage, and corrected status; Party transactions now honor the
  selected as-of date. Release/renewal exports include completion/reversal
  status. Sixteen selector/export tests and three focused tenant UI/document
  tests pass.

- P10's accepted operator-readiness slice orders business events newest-first, exposes correction
  only on the newest eligible event, explains later-event dependencies and
  preserves original-to-compensation evidence. The preflight shows source
  amounts, mode, delivery, and custody and requires an immutable administrator
  reason plus explicit confirmation. DEA mode remains posted-source-only;
  deferred mode may compensate only intact pending sources and creates no fake
  DEA identifiers. A posted source cannot be domain-only reversed after a mode
  change. Deferred full-release correction restores active lifecycle and
  in-vault custody through append-only evidence. Three focused mode/custody
  tests, the operator UI test, and the existing DEA newest-first regression
  pass.

- P9's accepted operator-readiness slice exposes frozen,
  observed, pending, discrepancy, and unresolved-blocker evidence; disables
  completion while expected items remain; provides a found-at-expected-location
  shortcut; and displays immutable resolution and compensation evidence. Each
  discrepancy now has one stable Owner-alert identity, with joined Notify job,
  attempt, failure, provider, and failed-only retry state. Nine focused
  collateral media/storage/verification tests and eight notice tests pass.

- P8's accepted operator-readiness slice links the current
  due/overdue report directly to preselected Interest Due or Overdue notices,
  requires confirmation of the displayed recipient and due snapshot, and
  exposes immutable Loans intent plus Notify event/job, attempt, failure,
  provider-reference, and retry evidence on loan detail. Historical reports do
  not expose a misleading current send action. Notice idempotency now rejects
  a changed explicit schedule as well as changed kind/channel/source. Eight
  notice-domain tests and three focused UI/evidence tests pass.

- P7 zero-balance top-up preview is corrected. Renewal eligibility now tests
  the resulting successor principal after applying both principal paid and
  top-up, rather than rejecting whenever the source outstanding principal is
  zero. An active zero-principal source can therefore close into a positive,
  collateral-backed successor; Pay and Renew still rejects a zero-principal
  result and directs the operator to full release. Focused preview, execution,
  accounting, and successor-balance regression coverage passes for a ₹5,000
  top-up from a ₹0 source balance.

- P7 successor-economics execution is complete. Release and Renew now requires
  an exact server-calculated preview before confirmation and freezes the fresh
  successor policy, item rates, advance interest, deducted fees, and gross-to-
  net cash handoff. The settlement event posts source dues/principal movement
  and successor deductions as separate gross facts; cash recognition credits
  interest income while accrual recognition credits Unearned Revenue. The
  successor opening carries per-item prepaid-interest evidence, so the first
  covered accrual consumes it without charging the borrower twice. Renewal
  agreement output and reconciliation expose the same values, and composite
  reversal reverses the complete voucher. A one-item compatibility call may
  infer its sole successor allocation; multi-item renewal requires an explicit
  allocation plan. Tenant migration `loans.0036` is applied to every local
  schema. Focused UI, document, DEA-contract, lifecycle, accrual, reporting,
  and reversal tests pass. P7 was accepted by the Owner on 2026-08-10.

- P6 full release was accepted by the workspace Owner on 2026-08-10 after the
  exact non-locking settlement quote, complete collateral handoff, closure,
  accounting disposition, and release document were exercised. P7 release and
  renew is active: prove the source settlement, selected return, retained and
  additional collateral plan, newly numbered successor, renewal agreement,
  accounting/custody evidence, and strict composite reversal as one clear
  operator workflow.

- P6 preview transaction hotfix is complete. The shared financial-action guard
  now distinguishes locking mutation checks from non-locking read previews;
  full-release GET and repayment preview no longer issue `SELECT ... FOR
  UPDATE` outside an atomic transaction. Regression coverage proves both
  previews avoid the locking loader, and a real non-atomic `jcl1` preview for
  PawnLoan 11 returned the exact settlement successfully.

- P6 full-release software execution is complete. The release screen now uses
  the same tenant-scoped, no-write calculation as confirmation, including
  release-day partial-period interest, and identifies every collateral item
  being returned. Confirmation requires an explicit exact-settlement and
  physical-handoff acknowledgement and reports the resulting release number,
  closure, item count, and real accounting disposition. Configurable active
  release/Form H layouts now fail document-integrity preflight when customer
  or authorized-staff signature evidence is absent. Eight focused release,
  UI, document, deferred-accounting, fail-before-write, partial-release
  prohibition, and strict-reversal tests pass; Django checks and Loans
  migration-drift checks are clean. Owner browser/document execution remains
  P6's acceptance step.

- P5 accrual and repayment was accepted by the workspace Owner on 2026-08-10.
  P6 full release is active: prove exact complete settlement, required accrual
  catch-up, immutable accounting and item-principal closure evidence, return of
  every remaining collateral item, storage removal, signed release/Form H
  output, loan closure, and strict reversal behavior.

- P5 software execution is complete. Eligible accruals expose per-collateral
  principal, metal rate, calculated interest, advance-interest offset, and
  newly due interest; finalized immutable lines remain visible on loan detail.
  Repayment now supports a canonical no-write allocation preview, displays the
  fixed priority and highest-rate-first principal impact, and reports its real
  accounting disposition after confirmation. Loan detail links to the Party
  statement and existing repayment receipt. Twenty-five focused tests, Django checks,
  and Loans migration-drift checks pass. Owner browser execution remains P5's
  acceptance step.

- P4 hierarchical storage was accepted by the workspace Owner on 2026-08-10.
  P5 accrual and repayment is active. Its domain core already provides
  itemized accruals, fixed fees/interest/principal priority, highest-rate-first
  tranche reduction, immutable allocation evidence, receipt generation,
  accounting disposition, and Party statements. The active gap is operator
  preview/readability before committing an accrual or repayment.

- P4 software execution is complete. The Owner's item scan or Place/Transfer
  action now selects the in-vault item in a workspace-scoped browser session;
  the next Box/Slot QR scan opens the transfer form with the destination
  selected. Successful movement clears the selection. Loan detail exposes the
  immutable storage movement ledger alongside current location. The complete
  8-test collateral media/storage/verification gate passes; Owner execution of
  initial placement and a reasoned transfer remains the P4 acceptance step.

- P3 physical identity was accepted by the workspace Owner on 2026-08-09 after
  the complete software gate and physical ticket, label, signature-area, and QR
  checks. P4 hierarchical storage is now active: prove the required Branch →
  Vault → Cabinet → Box/optional Slot path, initial placement, item and
  destination scan-assisted transfer, immutable movement evidence, capacity,
  and the current-location projection.

- P3 physical-identity audit found one configurable-document loophole: an
  active pilot ticket could include Original and Duplicate but omit required
  borrower/staff signature areas. Integrity diagnostics now reject that layout.
  Label evidence tests now prove loan number, immutable item code, description,
  Party, net weight, exact tenant QR target, and PDF hash. Fixed tickets already
  render both signed copies with one verification identity. The complete
  59-test document layout, rendering, persistence, media, label, and scan gate
  passes. The subsequent physical checks were accepted by the Owner.

- P2 mixed-metal origination and disbursal was accepted by the workspace Owner
  on 2026-08-09 after the number-visibility and deferred-accounting release
  corrections.

- Future Loans activation from `DEFERRED` back to DEA is now documented in
  proposed ADR `2026-08-09-loans-deferred-to-dea-activation.md`. The recommended
  default is an Owner-confirmed opening-position cutover: freeze an event
  watermark, preview active-loan/Party balances, post idempotent source-linked
  DEA openings, append coverage for pre-cutover pending outboxes, reconcile,
  then enable DEA. A preference toggle alone remains unsafe and unauthorized;
  the activation workflow is documented future work, not implemented runtime.

- PawnLoan release now respects the workspace accounting integration mode all
  the way through canonical balance and release readiness. In `DEFERRED`, an
  intact `PENDING` outbox is expected and no longer blocks repayment, accrual,
  release, or other dependent commands; missing, `FAILED`, and `PROCESSING`
  evidence still fail closed, and `DEA` mode still requires every event to be
  posted. A full deferred disbursal-to-release test proves pending source
  events, exact settlement, custody return, and loan closure without fabricated
  voucher evidence.

- P2 Owner walkthrough feedback found that the draft form did not expose the
  number represented by the selected series. The create page now shows the
  non-consuming next expected PawnLoan number for every selectable series both
  before and after economics preview, explains its concurrency boundary, and
  the saved-draft edit page shows the permanently allocated official number.

- P1 regulatory setup was accepted by the workspace Owner on 2026-08-09 after
  passing its complete software gate. P2 mixed-metal origination and disbursal
  passed its software gate and was subsequently accepted by the Owner.
  Its audit confirms that Loans owns per-item principal,
  effective-dated metal rates, mandatory draft photographs, item LTV,
  immutable approval evidence, and net-disbursal snapshots. The remaining
  operator gap was closed by attaching LTV failures to the offending
  allocated-principal field and exposing each tranche's rate, value, LTV limit,
  and interest in the draft economics preview. The complete 18-test draft UI
  suite and 11 focused domain/service tests pass.

- P1 regulatory setup passed its software gate. Migration `loans.0034`
  extends effective-dated workspace/license economic policy to own interest
  method, part-month slab, capitalization interval, cash/accrual recognition,
  and rounding alongside valuation/LTV/advance-interest. Approval freezes the
  complete resolved policy and disbursal builds its immutable snapshot from
  that evidence. The setup UI now exposes every agreed choice. The completed
  gates are 12 license/policy, 5 numbering/concurrency, and 3 focused
  setup/disbursal tests and 16 adjacent lifecycle/model tests, plus system
  check, migration drift, fresh tenant replay, and successful local tenant
  rollout through `migrate_schemas --tenant`.

- Loans is now the selected operational destination under accepted ADR
  `2026-08-09-girvi-capability-extraction-into-loans.md`. Girvi remains the
  temporary business-rule/capability reference and continues to own and service
  its existing records; no transfer, synchronization, dual write, or deletion
  is authorized. The former winner-selection pilot is replaced by twelve Loans
  acceptance gates. Each Girvi capability must be classified `PORT`, `REPLACE`,
  `RETIRE`, or `DEFER`, implemented without weakening Loans' aggregate,
  immutable-evidence, custody, tenant, correction, or accounting boundaries,
  and proven by operator evidence. P1 is accepted and P2 is active.

- The outstanding accounting/Girvi/Loans runtime checkpoint is consolidated
  into four dependency-ordered commits: `0e847b2` adds the guarded standalone
  accounting successor and audited preferences; `9ca47c9` makes Loans DEA
  delivery explicitly workspace-controlled and deferred by default; `cc7fc38`
  adds Girvi deferred disbursal/activation plus immutable TakenLoan repayment
  evidence with exact-replay conflict protection; and `7c74d07` retires three
  obsolete legacy data transforms for the accepted development-only/no-legacy-
  data boundary. The review fixed PostgreSQL settlement locking, stale immutable
  bootstrap and Loans tranche fixtures, and two idempotency conflict gaps.
  Completed gates are 110 accounting/configuration tests, 7 Loans readiness,
  6 Loans outbox, 30 Loans disbursal/lifecycle, 16 Loans draft/UI, 58 Girvi
  service/adapter/payment, and 6 Girvi tenant workflows. A fresh tenant migration
  replay through Girvi 0033, Loans 0033, and standalone accounting 0013 passes.
  Exact checkpoint `ab399e2` passes the split final preflight: 40 accounting
  kernel/projection, 4 clean-database concurrency, 33 accounting facade/UI,
  59 Loans, and 64 Girvi tests, plus system, diff, migration-drift, fresh tenant
  replay, and zero `jcl1` document-integrity findings. The named pre-pilot
  archive is validated. Twelve operator scenarios and the physical printer
  matrix remain before parity scoring can conclude.

- Loans operational-parity slice OP5 is complete. The audit confirmed existing
  customer intents already cover repayment, interest due, overdue, release,
  and auction. Tenant migration `loans.0033` adds immutable operational intents
  for the two real gaps: regulatory-license expiry and completed physical-
  verification discrepancy. Alerts snapshot their source and workspace Owner
  recipient, create idempotent Notify v2 jobs, join the tenant scheduler, and
  expose source-local create/retry controls. PostgreSQL enforces source tenant,
  source shape, and append-only evidence. OP6 essential reports and regulatory
  documents are now the final operational-parity blocker.

- Loans operational-parity slice OP4 is complete. Tenant migration
  `loans.0032` adds Owner-only physical-verification sessions, frozen
  Vault/subtree expectations, immutable found/missing/misplaced/unexpected
  observations, and separate resolution/compensation evidence. PostgreSQL
  enforces tenant/evidence agreement, the one-way completion transition, and
  append-only history. Unresolved discrepancies block storage transfer,
  release, release-and-renew, and FundingLoan pledge; location correction
  appends movement evidence and lost resolution requires current market value,
  negotiated compensation, and a cash-settlement reference. Damaged collateral
  stays blocked pending future policy. OP5 notices and OP6 essential
  reports/documents are next.

- Loans operational-parity slice OP3 is complete. Tenant migration
  `loans.0031` adds the required Branch/Vault/Cabinet/Box/optional-Slot tree,
  immutable placement/transfer/removal evidence, stable location QR identity,
  optional capacity, and one guarded collateral current-location projection.
  PostgreSQL enforces hierarchy, tenant consistency, movement order,
  projection agreement, and evidence immutability. Owner-only UI supports
  setup, location labels, initial placement, and reasoned transfer; unplaced
  in-vault collateral remains visibly awaiting placement. Release, auction,
  renewal, and renewal reversal maintain storage evidence. OP4 physical
  verification is next.

- Loans configurable documents now have an accepted cleaner target pipeline:
  published layouts own logical Original/Terms/Duplicate/D3 content and
  mandatory evidence, while immutable workspace print-profile revisions will
  own A5/A4 imposition, copy bundles, page order, simplex/duplex, orientation,
  scaling, and printer guidance. Official issues must snapshot the resolved
  profile revision/hash and retain exact PDF bytes. This is documentation and
  architecture approval only; current embedded layout composition remains
  authoritative until LPD7 compatibility migration and parity tests pass. OP3
  hierarchical storage remains the next operational-parity slice.

- Loans operational-parity slice OP2 is complete. Tenant migration
  `loans.0030` adds unique immutable collateral UUIDs, append-only photograph
  evidence, and audited label issues with PostgreSQL mutation guards. Draft
  edits now preserve item identity; new UI collateral requires JPEG/PNG media;
  approval freezes photo IDs and SHA-256 hashes and fails closed on missing
  evidence. Release-and-renew inherits retained-item provenance and requires
  fresh media for additions. Labels carry the agreed loan/item/Party/weight
  fields and tenant-scoped QR navigation. The focused 3-test media suite passes;
  34/35 adjacent draft/lifecycle/UI tests pass, with the sole failure belonging
  to the separate dirty accounting-readiness work. OP3 hierarchical storage is
  next.

- Loans operational-parity slice OP1 is complete. Tenant migrations
  `loans.0027` through `loans.0029` add immutable issue/amendment/renewal
  license revisions, document evidence, exact PawnLoan-to-revision binding,
  portable index names, and PostgreSQL immutability/consistency guards. The
  Owner/Admin setup UI now includes license readiness and expiry blockers,
  revision history, secure evidence download, renewal, and a license-register
  PDF. Focused regulatory/service tests pass (10), the setup-browser test
  passes, and the adjacent draft/lifecycle/document suite passed after fixing
  its only exposed release-item validation defect. External email/SMS expiry
  delivery remains OP5. OP2 collateral photographs and labels are next.

- The intended Girvi/Loans end state is Loans consolidation followed by
  evidence-based Girvi retirement. Strict source ownership remains in force.
  The first Loans capability pass was blocked
  on regulatory operations, collateral photos/labels, hierarchical storage,
  physical verification, and the required notices, reports, statements, and
  regulatory documents. Named bulk actions are useful follow-up work, not a
  first-pilot blocker. Draft collateral photographs are mandatory. The MVP
  label carries loan, item, description, Party, weight, and QR identity. Only
  the confirmed daily/regulatory reports and forms block the pilot. Their list
  now covers active/daily/interest/overdue/release/storage/license/Party reports
  and ticket/receipt/Form H/renewal/notice/license forms. Missing or misplaced
  collateral blocks release, renewal, repledging, and storage transfer until
  administrator resolution.
  Post-approval photos are append-only, storage permits one current location
  per item with item/destination scanning, and verification supports whole-vault
  or subtree scope. Loan tickets and releases require customer/staff signatures;
  ticket copies share one document number and are labelled Original/Duplicate.
  Storage transfer and physical verification are Owner-only for the pilot.
  A Custodian role may receive those permissions later. Lost-collateral
  resolution requires a cash settlement based on current market value, with
  the final amount negotiated; required evidence remains open.
  Storage follows the fixed Branch/Vault/Cabinet/Box hierarchy with an optional
  Slot and no skipped levels. Initial placement may follow disbursement and is
  shown as awaiting placement. Signatures may be handwritten or digital. The
  damaged-collateral release policy remains deferred.

- Loans consolidation and eventual Girvi retirement are now under accepted ADR
  `2026-08-09-girvi-capability-extraction-into-loans.md` and the active fit-gap
  plan. Strict independent ownership still controls runtime
  during temporary coexistence; no Girvi removal, record transfer, migration
  deletion, route removal, or FundingLoan enablement is authorized. The first database-free
  FundingLoan Gate A probe now passes all 15 focused tests. It proves separate
  immutable terms/lifecycle, monthly simple interest, repayment allocation,
  event-folded balances, multi-PawnLoan collateral, pledge/return LTV, financial
  plus custody closure, and exact newest-first financial/custody correction
  without ORM or accounting. Gate B persistence/application design is now
  accepted in `funding-loan-gate-b-persistence-design.md`: it specifies the
  table and constraint map, operational events separate from accounting,
  repository/command/null-adapter ports, deterministic lock order, partial
  unique active pledges, PostgreSQL immutability/cross-table guards, migration
  sequence, and test matrix. Gate B schema slice 1 is complete: additive
  FundingLoan sequence/aggregate/terms/event/pledge/return models are in tenant
  migrations `loans.0019` and `loans.0020`; the canonical custody stream now
  accepts funding pledge and return sources; row constraints and reversible
  PostgreSQL guards enforce lifecycle, immutable evidence, exact newest-first
  financial reversals, pledge eligibility/uniqueness, return evidence, and
  custody continuity/projection. Gate B application slices 2-3 now add locked
  workspace numbering, draft/cancel, atomic multi-PawnLoan activation,
  canonical replay/conflict handling, interest/fee/repayment events,
  settlement, LTV-safe partial/full return, and financially plus custodially
  gated closure through null outbound delivery. A two-connection race proves
  one winner for a shared collateral pledge, failure injection proves full
  operational rollback, and migration `loans.0021` makes a bounded sequence's
  maximum allocatable exactly once. The combined 34-test FundingLoan domain,
  persistence, application, concurrency, and registration gate passes on fresh
  tenant schemas. Gate B is now complete: locked financial reversal enforces
  exact newest-first compensation, and immutable FundingPledgeReversal plus
  FundingReturnReversal evidence exactly compensates custody while atomically
  synchronizing pledge membership and projections. Reversal-aware return
  uniqueness permits corrected re-return without changing history. PostgreSQL
  guards enforce immutable evidence, matching source, exact/latest inversion,
  and one compensating movement per item. Additive tenant migrations
  `loans.0022` through `loans.0025` carry this boundary. The final 40-test
  FundingLoan gate plus one legacy auction-custody regression passes on fresh
  tenant schemas; Loans migration drift and diagnostics are clean. Gate C may
  begin with read-only selectors and integrity findings, but runtime support,
  navigation, write UI, Girvi, and accounting remain untouched. Gate C's
  read-only foundation is now complete: tenant-scoped immutable list/detail
  rows fold balances only from FundingLoan events, expose terms and active
  collateral, combine financial and custody correction evidence into one
  timeline, and report event, activation, custody projection, and closure
  integrity findings without mutation. Focused tenant, corrected-lifecycle,
  clean-integrity, and corrupted-projection tests pass within the full 40-test
  FundingLoan suite. No route, template, flag, accounting query, Girvi change,
  or migration was added. Gate C now also has an unlinked Owner/Admin-only read
  console and detail page under Loans setup. They render only selector output,
  expose no write controls, reject ordinary members, fail closed for unknown or
  cross-workspace identifiers, and continue to show runtime/accounting as
  disabled. Focused permission, render, not-found, and disabled-runtime tests
  pass. Fresh schema replay no longer executes the retired Girvi conversions
  for RepledgedLoanItem, legacy Loan to GivenLoan/TakenLoan, or LoanPayment to
  draft DEA vouchers; their migration graph nodes and schema operations remain
  intact, and existing migrated databases are unaffected. The next Gate C slice
  was the unlinked Owner/Admin draft and lender-capture flow and is now
  complete. The hidden console lists only active Party lenders; submission uses
  the existing transactional command, allocates the workspace number, records
  the actual actor, and redirects to read detail. Invalid/inactive Party input
  creates no draft and consumes no sequence. Draft completion is now also
  delivered through additive migration `loans.0026`: Owner/Admin users can
  save policy-validated terms and eligible active, appraised, in-vault Pawn
  collateral as mutable pre-activation input. Detail shows LTV readiness while
  custody and immutable activation evidence remain unchanged. Cancellation
  requires a reason and records immutable actor/reason evidence. Focused
  service and tenant UI tests cover rollback, eligibility, permissions,
  readiness, zero draft/cancelled balances, and cancellation. Controlled
  activation is now delivered behind exact `ACTIVATE` confirmation. It locks
  and revalidates the saved proposal through the existing atomic activation
  service, creates immutable terms/event/pledge/custody evidence, removes draft
  inputs only after success, and rolls back cleanly when collateral has become
  stale. Runtime and public navigation remain disabled, and no accounting is
  emitted. Hidden Owner/Admin repayment capture is now delivered through the
  existing locked service: browser request keys replay exactly, overpayments
  fail without evidence, allocations remain fees then interest then principal,
  and actor evidence is retained. Detail now renders a reversal-aware statement
  derived only from immutable FundingLoan events with component effects and
  running balances. Runtime, public navigation, and accounting remain disabled.
  Hidden settlement review and controlled collateral return are now delivered.
  Review starts only for a zero-balance active loan; readiness distinguishes
  financial settlement from custody completion; returns are available only
  while settlement is pending and delegate LTV, active-pledge, locking, and
  exact replay rules to the existing service. Immutable return and custody
  evidence records the actor and restores branch-vault custody. Runtime,
  public navigation, and accounting remain disabled. Hidden controlled closure
  is now delivered: settlement initiation itself requires zero balance, the
  closure form requires exact `CLOSE` confirmation, and the locked closure
  service recomputes zero balance plus complete vault return before recording
  terminal state and actor. Repeated closure is idempotent and closed detail is
  read-only. Gate C is now complete: hidden reason-required financial, return,
  and whole-pledge correction controls expose only selector-approved targets
  and delegate final authorization, locking, newest-first ordering, custody
  policy, immutable compensating evidence, actor capture, and exact replay to
  the existing services. Fixed preview PDFs provide agreement/handoff,
  repayment receipt, collateral return receipt, and event-derived statement
  artifacts with source-linked verification IDs and explicit accounting-not-
  posted wording; they create no persisted document issues and do not extend
  configurable layouts. The end-to-end tenant workflow covers correction
  replay and projection plus all four PDFs before settlement, return, and
  closure. Runtime support, public navigation, Girvi changes, accounting
  delivery, and persisted/configurable FundingLoan documents remain deferred.
  Gate D is now the Girvi-capability-extraction and Loans-acceptance boundary.
  FundingLoan's Owner/Admin operational core and the required regulatory,
  collateral-media, label/QR, hierarchical-storage, physical-verification,
  notice, report, and form capabilities are implemented. The acceptance pass
  must retain source, financial fold, custody/location fold, document,
  permission/tenant, accounting-disposition, exception, and backup/restore
  reconciliation evidence. Money, custody, tenant, required-document, or
  unexplained reconciliation failures are blocking. The twelve scenarios run
  against Loans; Girvi supplies mature rules and expected outcomes where needed.
  P1 regulatory setup is the next acceptance gate. FundingLoan runtime, normal
  navigation, and accounting delivery remain disabled meanwhile.
  The in-place Girvi
  rebuild ADR and plan are on hold as the fallback if consolidation exposes a
  fundamental product or architecture mismatch.
- A destructive Girvi operational-core rebuild is proposed under ADR
  `2026-08-08-girvi-operational-core-rebuild.md` and the paired execution plan.
  The target keeps the Girvi product/app identity but replaces its internal
  models, migration history, transition registry, service aggregation, DEA
  payment coupling, Customer bridge, routes, and tests. The new core models
  explicit customer-loan and funding-loan aggregates, Party-only identity,
  immutable operational events, projected balances/custody, dedicated use-case
  handlers, and null accounting adapters. Full customer and funding servicing,
  corrections, documents, jobs, and integrity must pass with accounting
  disabled before any versioned accounting outbox is connected. The proposal
  requires owner confirmation of the scope decision table and destructive
  migration-baseline replacement before implementation starts. This proposal
  is now on hold during the Loans consolidation fit-gap evaluation.
- Operational accounting integration is now reversible and deferred by default
  under ADR `2026-08-08-operational-accounting-integration-deferral.md`.
  Audited workspace preference `accounting__integration_mode` selects
  `DEFERRED` or `DEA`. Loans always preserves immutable source events and
  outboxes; deferred events remain truthfully `PENDING`, skip DEA readiness and
  automatic delivery, and do not block later business actions. Explicit `DEA`
  mode preserves the existing posting, dependency, idempotency, and reversal
  contracts. Existing accounting history is untouched. Girvi `GivenLoan`
  disbursal is now the first decoupled vertical: deferred workspaces record one
  canonical, idempotent `DISBURSAL` outbox event without DEA party-account
  resolution or a `PaymentVoucher`; explicit `DEA` mode retains the existing
  posted voucher. `TakenLoan` activation now has the same boundary through the
  newly persisted `TAKEN_LOAN_ACTIVATION` event vocabulary. `TakenLoan`
  repayment now persists immutable Girvi-owned `LoanRepayment` evidence,
  deduplicates against it, folds it with only unlinked historical DEA vouchers,
  and emits `TAKEN_LOAN_REPAYMENT` while deferred without creating a
  `PaymentVoucher`. Database guards prohibit evidence update/delete and enforce
  exact compensating reversal rows. `GivenLoan` repayment and the remaining
  release, accrual, recovery, renewal, write-off, and reversal slices are still
  deferred. Real DEA TakenLoan activation/repayment posting currently has an
  unrelated existing defect: its posting rules omit the required
  `DualLedgerLine.currency` argument.
- Permanent independent Girvi/Loans coexistence is accepted under ADR
  `2026-08-08-girvi-loans-permanent-independent-coexistence.md`. Both apps may
  originate new records and permanently own their own lifecycles; neither app
  copies, transfers, or mutates the other's records. Accounting delivery is
  independently controlled by the workspace integration mode. The existing
  Loans feature flag is transitional route-default
  behavior, not an ownership switch. The next engineering slice replaces it
  with independent Girvi/Pawn Loans availability plus a default-module setting
  and separate navigation identities.
- Girvi destructive legacy cleanup is complete on branch `dea-kiss` under ADR
  `2026-08-08-girvi-canonical-cleanup-and-coexistence-retirement.md`.
  Deprecated `Loan`/`LoanPayment` runtime models and resources are deleted;
  `girvi.0029` removes their schema state; active `LoanChangeLog` is independent
  in `models/audit.py`; and runtime models/managers now use canonical
  `models/loan.py` and `managers.py` modules. Legacy lifecycle status and
  transition aliases are removed. Notify no longer has a direct Girvi-loan M2M
  and uses generic notification items. Girvi/Loans unified reads, comparison,
  command/view/template, and coexistence readiness evidence are retired.
  Fresh tenant migration replay, 64 affected cross-app tests, focused lifecycle
  and import tests, Django checks, and migration drift checks pass. The full
  `apps.tenant_apps.girvi.tests` package is now a tenant-aware executable gate:
  database-backed series guardrail tests provision isolated tenant schemas, and
  all 409 tests pass. The destructive schema reset runbook remains unexecuted
  pending explicit target-schema approval.
- Girvi cleanup follow-up on branch `dea-kiss` advanced through Wave 3:
  legacy compatibility seams were removed (`models/legacy.py`, disabled legacy
  commands, deprecated managers, posting adapter re-export), runtime imports
  were rewired to direct DEA adapter boundaries, and Girvi create routes no
  longer depend on the Loans cutover facade. Focused Girvi suites and
  `loans.tests.test_feature_gate` pass after startup/import regressions were
  stabilized. Wave 4 (destructive schema reset plan) and Wave 5 (canonical
  naming/test-suite cleanup) are now documented in
  `docs/plans/girvi-audit-followup-plan.md` for next execution slices. The
  Wave 4 execution runbook is now available at
  `docs/implementation/girvi-destructive-schema-reset-runbook.md`.
  Wave 5 is complete: `models/loan.py` now owns canonical `GivenLoan` and
  `TakenLoan`, deprecated `Loan`/`LoanPayment` live in `models/legacy_loan.py`,
  and an AST guard prevents transitional `loan_refactored` imports while
  confining legacy imports to package registration and import/export. Django
  detects no migration changes and the final focused Girvi/Loans suite passes
  all 72 tests.
- Standalone accounting now exposes visual immutable reversal from posted
  voucher detail. Owner mode accepts the real Owner's reversal date, mandatory
  reason, and typed `REVERSE` confirmation; Team mode preserves the
  different-user rule. Original and reversal vouchers remain linked and
  visible. Reversed credit-sale items report zero outstanding and reject new
  allocations; allocated invoices require receipt reversal first. The focused
  UI test is implemented but its run is currently blocked before Django setup
  by unrelated user-owned Girvi edits importing a removed `LoanManager`; those
  edits were preserved.
- Standalone accounting customer identity now uses tenant `party.Party`.
  Migration `0013_external_account_party_link` adds the protected Party FK and
  enforces one external account per book/Party/purpose for linked accounts.
  Visual sale/receipt entry selects an active Party or creates one inline, then
  resolves its customer-receivable account and classification. Existing
  synthetic adapter accounts remain nullable compatibility evidence. The owner
  flow tenant test passes; `0013` is applied and verified in all five local
  tenant schemas; migration drift and Django checks are clean.
- Standalone accounting now has the simplified owner-operated MVP. Audited
  workflow mode defaults to `OWNER`: one actual workspace Owner confirmation
  truthfully records that Owner as maker, authorizer, and poster while retaining
  immutable lifecycle evidence. `TEAM` retains separate actions. Entry can
  create a missing standalone customer receivable/classification inline. A
  tenant test proves one Owner request creates the customer, posts the invoice,
  and creates its open item. The authorization ADR records this explicit
  segregation-of-duties waiver; nobody is impersonated.
- Standalone accounting activation is now owner-operable at
  `/accounting/activation/`. The page displays live readiness blockers and the
  accepted narrow scope, requires the exact phrase `ENABLE ACCOUNTING` when
  turning writes on, delegates to the audited fail-closed activation service,
  and supports immediate disablement without changing posted evidence. It does
  not claim DEA replacement or import existing data.
- Standalone accounting K8.2 setup UX now handles an uninitialized workspace.
  When no PRIMARY book exists, `/accounting/` shows an Owner/Admin-only
  “Initialize accounting” action. `/accounting/setup/` collects the financial
  period key and dates, then calls the authenticated idempotent bootstrap to
  create the tenant-bound INR book and Cash/Receivables/Sales ledgers. It does
  not import DEA or enable posting. This resolves the previously unactionable
  “Exactly one PRIMARY accounting book is required” readiness message.
- Standalone accounting K8.2b visual transaction workflow is complete for the
  MVP scope. When the tenant activation gate is enabled, accounting users can
  create cash-sale, credit-sale, and customer-receipt drafts; a different
  authorized user approves; and a user different from the authorizer posts.
  The UI explicitly blocks maker self-authorization, facade posting already
  blocks authorizer self-posting, credit-sale posting atomically creates its
  open item, and posted receipts can be explicitly allocated without another
  financial posting. A real three-session tenant test proves Member maker,
  rejected maker approval, Admin authorization, Owner posting, and open-item
  evidence. K8.3 pilot visual UAT and controlled target enablement is next.
- Standalone accounting K8.2a delivers the first visual successor workspace.
  Authenticated tenant members with accounting access can open `/accounting/`,
  see readiness/enabled state, headline balances and recent posted vouchers,
  inspect voucher actor/source evidence and conventional journal lines, and
  view trial balance, P&L, balance sheet, and open items at
  `/accounting/reports/`. The screens remain read-only and work while the gate
  is disabled; tenant middleware and view permissions reject outsiders. Two
  focused route/render/access tests pass. K8.2b is next: a real staged
  maker-authorizer-poster UI, never automatic actor impersonation.
- Standalone accounting K8.1 activation safety is complete. Audited tenant
  preference `accounting__successor_enabled` defaults off and can be changed
  only by an accounting administrator in the matching active tenant. Enabling
  fails closed unless the tenant-bound PRIMARY book, required MVP ledgers, an
  open period, and clean integrity diagnostics are present. Focused default,
  authorization, audit, and blocker tests pass. The K7 UAT tenant reports ready
  with zero blockers but remains disabled. K8.2 is now the first visual MVP:
  dashboard, sales/receipt entry, voucher/journal evidence, and core reports.
- The project owner accepted the K7.6 evidence on 2026-08-07 and explicitly
  chose to proceed without independent accountant review because that resource
  is unavailable. The waiver is recorded as owner risk acceptance, not an
  accountant endorsement. K7 is now a conditional GO only for preparing the
  tested INR sales/customer-receipts caller behind an off-by-default control.
  Tax/statutory scope, other adapters, data migration, and DEA replacement are
  still excluded; DEA remains authority until target-tenant verification and
  explicit enablement.
- Standalone accounting K7.6 engineering evidence is complete. The read-only
  `accounting_evidence_pack` command exposes vouchers and actor snapshots,
  conventional journal, trial balance, statements, external balances, open
  items, receipt allocation/unapplied amounts, reversal lineage, source
  deliveries, and integrity findings. A fresh normally provisioned
  `accounting_pilot_k7_uat` tenant used distinct maker/authorizer/poster actors
  and the actual source adapter for cash sale, credit sale/open item, partial
  receipt allocation, reversal, and corrected source version. Its trial balance
  and balance sheet balance, diagnostics have zero findings, and all 10 facade
  integration tests pass. The owner subsequently accepted this evidence with a
  documented professional-review waiver and authorized only the narrow next
  production-boundary step; DEA remains authority.
- Standalone accounting K7.5 assurance is complete. The read-only tenant
  integrity command checks posting cardinality/subtypes, fingerprints, actor
  evidence, reports, classifications, allocations, and failed delivery state.
  Four real separate-connection races prove exact delivery replay,
  changed-payload rejection, reversal replay, and allocation capacity. The
  `accounting_pilot_mvp` dump restored into an isolated temporary schema; all 16
  accounting table counts and diagnostics matched, and cleanup completed. The
  operations runbook documents stop/preserve/retry/escalate behavior. K7.6 is
  staging UAT and independent go/no-go; DEA remains authority.
- Standalone accounting K7.4 is complete without widening the MVP. A frozen
  schema-v1 DTO and one adapter post only INR cash sales, credit sales, and
  customer receipts through distinct facade maker/authorizer/poster actors.
  Canonical payload hashing makes exact replay idempotent and rejects changed
  reuse; an outer transaction prevents partial vouchers while durable delivery
  rows retain failure/retry evidence. PostgreSQL freezes source identity and
  posted delivery state. Migration `0012` is applied to all four local tenant
  schemas with zero seeded deliveries. All 87 accounting tests pass. K7.5 is
  diagnostics, concurrency, and recovery assurance.
- Standalone accounting K7.3 is complete and MVP-bounded. Admin/Owner-only
  facade operations now bootstrap exactly one primary INR book, supplied period,
  and Cash/Receivables/Sales ledgers idempotently, failing on configuration
  conflict. Periods follow an audited Open/Adjustment-only/Closed/Locked state
  machine; reopening requires a reason, Locked is terminal, evidence is
  immutable, and PostgreSQL rejects state changes without the latest matching
  evidence. Tenant migrations `0010`/`0011` are applied to all four local
  schemas. All 84 accounting tests pass. K7.4 is the narrow source adapter.
- Standalone accounting K7.2 is complete without broadening the MVP. Facade
  creation records an immutable actor snapshot and atomically assigns
  `BOOK-YEAR-NNNNNN` from a locked per-book/period-year sequence; authorization
  and posting also retain identity snapshots independent of later user-profile
  changes. Tenant migrations `0008` and `0009` backfill existing pilot evidence,
  add database constraints/guards, and are verified in `jcl1`, `jsk`, `test`,
  and `accounting_pilot_mvp` with no missing evidence. All 82 accounting tests
  and the live pilot pass. K7.3 is period lifecycle and deterministic bootstrap.
- Standalone accounting K7.1 is complete. The production facade requires an
  authenticated active user, exact current-schema/workspace binding, and
  explicit create/authorize/post/reverse permissions. Members prepare drafts;
  Admins/Owners operate lifecycle actions; the server owns timestamps; an
  authorizer cannot post the same voucher even through a stale object; and the
  original poster cannot approve its reversal. Four tenant-backed facade tests
  pass. No URL, source adapter, UI, or production caller was added. K7.2 is
  durable actor evidence and atomic annual voucher numbering.
- The K6 accountant-style review passed for the synthetic scope after adding an
  explicit unapplied-settlement projection: receipt `PILOT-2026-0003` now shows
  INR 600 received, INR 400 allocated, and INR 200 unapplied. The live pilot and
  all 77 accounting tests pass. K7 production-boundary planning is now open in
  `docs/plans/standalone-accounting-k7-production-boundary.md`; DEA remains the
  production authority and independent acceptance remains required before go-live.
- The disposable `accounting_pilot_mvp` tenant was provisioned through the
  normal onboarding path and the guarded K6 harness ran twice with identical
  evidence: five posted vouchers, ten journal lines, balanced trial balance and
  balance sheet, zero classification difference, INR 1,900 result, INR 400
  receivable balance, and INR 600 open-item outstanding. DEA tables remained at
  their standard-seed baseline. This clears technical sandbox execution and
  replay checks only; owner/accountant sign-off is next and all production
  gates remain shut.
- The recommended K6 pilot defaults are accepted in ADR
  `2026-08-07-standalone-accounting-pilot-policy`: correctness-first,
  synthetic-only, sales/receipts first, tenant owner as sandbox operator, and
  independent annual accounting voucher numbers with separate source identity.
  A guarded idempotent `run_accounting_acceptance_pilot` command now bootstraps
  and verifies the five-voucher synthetic cycle only under `DEBUG` in an
  existing `accounting_pilot_*` tenant owned by the supplied actor. All 77
  accounting tests pass. The local technical run is recorded in
  `docs/implementation/standalone-accounting-acceptance-pilot.md`.
- Standalone accounting K6 readiness review is complete. Decision: GO only for
  an isolated, synthetic, non-production acceptance pilot; NO-GO for production
  posting, production shadow traffic, DEA replacement, or data migration. The
  76-test persisted kernel, seven tenant migrations, tenant/public isolation,
  empty local successor tables, and report invariants are sound. Production is
  blocked by the missing authenticated facade/permissions, durable audit
  identity and voucher numbering, controlled period lifecycle, deterministic
  bootstrap, source adapter, diagnostics, recovery rehearsal, concurrency
  tests, and accountant pilot sign-off. The complete gate and smallest pilot
  are recorded in `docs/plans/standalone-accounting-mvp-readiness.md`.
- Standalone accounting K5.8 completes the persisted MVP kernel proof without a
  migration. Read-only selectors adapt posted ORM rows to the proven K2 domain
  contracts and expose conventional journal lines, separate internal/external
  balances, trial balance, P&L, balance sheet, and frozen-classification
  reconciliation. A persisted credit-sale/receipt test balances, reports ₹300
  current-period result, reconciles to zero, excludes drafts, and performs no
  writes. All 76 focused tests pass. No reporting table, cache, UI, runtime
  adapter, or cutover was added. Further implementation should pause for a K6
  MVP readiness review and smallest-pilot decision; DEA remains production
  authority.
- Standalone accounting K5.7 is complete and deliberately MVP-bounded. When a
  settlement batch is reversed, its immutable allocations now receive exact
  compensating rows linked to the financial reversal transaction; original
  allocations remain untouched and outstanding capacity is restored by a net
  fold. PostgreSQL verifies item, money, currency, and reversal lineage. All 75
  focused tests pass. Tenant migration `standalone_accounting.0007`, its column,
  and revised guard are verified in `jcl1`, `jsk`, and `test`; no data, UI,
  allocation engine, reporting cache, runtime adapter, or cutover was added.
  K5.8 should be read-only ORM projections over persisted truth. DEA remains
  production authority.
- Standalone accounting K5.6 is complete. Tenant migration
  `standalone_accounting.0006` adds immutable open items and non-financial
  allocations over posted external-account transactions. Open items freeze the
  exact originating book/account/currency amounts; settlements must be posted,
  opposite-side, and on that same boundary. Locked services and PostgreSQL
  guards prevent concurrent or bypass over-allocation and all mutation/deletion.
  Outstanding amounts are derived, and allocations create no accounting
  transaction. All 74 focused tests pass. Both tables and guards are verified
  in `jcl1`, `jsk`, and `test`; no rows were seeded or runtime callers connected.
  K5.7 is compensating allocation evidence for reversed settlements, then
  persisted reporting projections. DEA remains production authority.
- Standalone accounting K5.5 is complete. Reversal is now append-only new
  evidence: a new adjustment voucher retains every monetary fact and frozen
  external classification, reverses transaction order, swaps each side, and
  posts as a batch linked to the untouched original. PostgreSQL verifies exact
  opposite shape, one reversal per original, no reversal-of-reversal, and
  mandatory reason evidence. Correction atomically combines this reversal with
  an authorized replacement under a correction group. All 71 focused tests
  pass. Tenant migration `standalone_accounting.0005` and the exact-reversal
  trigger are verified in `jcl1`, `jsk`, and `test`; no rows were seeded or
  runtime callers connected. DEA remains production authority. K5.6 is open
  items and non-financial allocation evidence.
- Standalone accounting K5.4 is complete. Tenant migration
  `standalone_accounting.0004` adds one immutable posting batch per posted
  voucher. The canonical service locks authorized intent and its period,
  enforces ordinary/adjustment period policy, derives a deterministic economic
  fingerprint, and commits the posted state plus batch atomically. Deferred
  PostgreSQL cardinality prevents either half from existing alone; database
  guards freeze both afterward. Exact replay returns the original batch. All 67
  focused tests pass, and migration/table verification passed in `jcl1`, `jsk`,
  and `test` with no seeded rows or runtime integration. DEA remains production
  authority. K5.5 is append-only reversal and correction execution.
- Standalone accounting K5.3 is complete. Tenant migration
  `standalone_accounting.0003` adds auditable voucher headers and one common
  monetary transaction row with exactly one ledger or external-account
  subtype. PostgreSQL guards enforce deferred exact subtype cardinality,
  same-book posting sides, base-currency conversion, frozen effective
  classification, and immutable authorized intent. All 63 focused tests pass.
  `migrate_schemas --tenant` applied and all four tables were verified in
  `jcl1`, `jsk`, and `test`; no rows were seeded. DEA remains runtime authority.
  K5.4 is posting batches plus the atomic posting repository/service.
- Standalone accounting K5.2 is complete. Tenant migration
  `standalone_accounting.0002` adds book-owned external accounts with explicit
  Party adapter keys/accounting purposes and immutable effective-dated
  classification versions. PostgreSQL guards prevent overlapping ranges,
  cross-book/non-posting reporting ledgers, reporting class/normal-side
  mismatch, core mutation, and deletion. The only allowed version mutation is
  one-time closure of an open range by the locked append service before its
  successor is created; the selector resolves exactly one posting-date version
  or fails. All 57 focused tests pass. `migrate_schemas --tenant` applied and
  verification passed in `jcl1`, `jsk`, and `test`; no rows were seeded and DEA
  remains runtime authority. K5.3 is voucher headers plus draft atomic
  transaction/subtype persistence, without posting batches or runtime posting.
- Standalone accounting K5.1 is complete. The successor is registered in
  `TENANT_APPS`, and tenant migration `standalone_accounting.0001_initial` adds
  only `AccountingOrganization`, `AccountingBook`, `AccountingPeriod`, and
  `Ledger`. Books own base-currency scale; periods have status/evidence checks
  and a PostgreSQL per-book overlap exclusion; ledger masters carry reporting
  class, normal side, node kind, debit/credit permissions, and database guards
  against cross-book parents, posting parents, and cycles. All 52 focused tests
  pass, including model-validation bypass and public-vs-tenant table checks.
  `migrate_schemas --tenant` applied and verification passed in `jcl1`, `jsk`,
  and `test`. No rows were seeded, and current DEA remains runtime authority.
  K5.2 is external accounts plus immutable classification versions only.
- Standalone accounting K4 is complete. `AccountingConfig` now gives the
  successor package a stable Django identity (`standalone_accounting`) while
  structural tests keep it absent from runtime settings and verify that models,
  migrations, URLs, and admin remain absent. The accepted persistence design at
  `docs/implementation/standalone-accounting-persistence-design.md` maps the
  full relational boundary and chooses one transaction row lifecycle: editable
  under a draft voucher, immutable once its posting batch exists, with no copied
  posted-transaction table. It specifies organization/book ownership, periods,
  ledger hierarchy, external classification, exclusive transaction subtypes,
  batches, reversals, allocations, database triggers, and projections. All 44
  K0-K4 tests pass. K5.1 is the first separately reviewed model/schema slice.
- Standalone accounting architecture proof K3 and the formal architecture gate
  are complete. Pure contracts now cover immutable voucher authorization,
  source/rule version identity, deterministic fingerprints, book-scoped exact
  replay and changed-payload rejection, open/adjustment-only/closed/locked
  period behavior, transaction-to-base currency validation, append-only
  reversal, and correction as reversal plus replacement. All 40 K0-K3 tests
  pass. ADR `2026-08-07-standalone-accounting-transaction-kernel.md` is now
  accepted because scenarios and financial reports derive from one transaction
  truth without duplicate control postings. Current DEA remains runtime owner;
  no app registration, schema, migration, route, or integration changed. K4 is
  an unregistered Django skeleton and persistence design review.
- Standalone accounting architecture proof K2 is complete. Independent pure
  projections now expose two conventional journal lines per atomic pair,
  internal-ledger and external-account balances, a combined balanced trial
  balance, P&L, and a balance sheet with derived current-period result. Frozen
  external classifications enter reports exactly once; reconciliation proves
  external detail plus direct internal activity equals the reporting-ledger row.
  Later reclassification does not rewrite history, and reversal neutralizes all
  projections. All 27 K0-K2 tests pass. K3 voucher/idempotency/period/currency/
  correction/source contracts remain before the proposed ADR acceptance gate.
- Standalone accounting architecture proof K1 is complete. The executable
  scenario corpus covers cash and credit sales, a partially allocated customer
  receipt, supplier purchase/payment, loan disbursal, principal-interest-fee
  repayment, an explicitly paired many-sided manual journal, and whole-batch
  reversal. A pure open-item settlement contract keeps allocation explanatory:
  it cannot create financial effects, exceed its account transaction, or cross
  external accounts. All 19 K0/K1 tests pass. No Django/runtime behavior changed.
  K2 pure projections and financial-statement reconciliation are next and remain
  the decisive no-double-counting architecture test.
- Standalone accounting architecture proof K0 has started. Proposed ADR
  [2026-08-07](adr/2026-08-07-standalone-accounting-transaction-kernel.md)
  adapts the supplied *Ledger - Double Entry* schema into a side-by-side,
  unregistered `apps.tenant_apps.accounting` proof package. The database-free
  kernel defines positive atomic ledger-to-ledger and ledger-to-external-account
  transactions, frozen external-account classifications, ordered compound
  batches, monetary/base values, and exact reversal. Nine focused tests pass.
  No Django app registration, models, migrations, URLs, current-DEA behavior,
  or cross-app integration changed. The ADR remains proposed until K1-K3 prove
  scenario coverage, reports without double-counting, historical classification,
  periods, idempotency, and currency contracts.
- Loan-ticket-only overlay sheet composition is complete. A5 logical surfaces now separate
  Original front, Original Terms, Duplicate front, and Duplicate D3 assets;
  blocks are scoped to Both/Original/Duplicate. Eight deterministic presets
  cover individual A5 output, A5 simplex/duplex sequences, and one- or two-page
  A4-landscape side-by-side imposition. Each generated front copy independently
  requires mandatory fields/tables/verification, and every required background
  fails closed if absent. The visual overlay editor exposes presets, four
  surface assets, and copy scope. Printer flip-edge selection remains a physical
  acceptance responsibility.
- The visual overlay editor is complete for Owner/Admin absolute-overlay
  drafts. An authenticated first-page background raster is shown behind scaled
  block rectangles; drag updates top-left X/Y inputs, while numeric forms own
  exact geometry, type, binding, image asset, text, font size, and alignment.
  Operators can add/remove supported blocks, choose page/background/copy
  settings, and preview/test-print. Every mutation uses `update_draft` and the
  full overlay validator; advanced JSON remains for detailed table/condition/
  overflow and duplex back-page properties.
- Absolute-overlay schema and renderer are complete. Owner/Admin users can
  create an Exact PDF overlay starter that requires `form.background` and uses
  bounded whole-millimetre rectangles measured from the page's top-left.
  Registered fields, title, image, QR, verification, signature, and table
  blocks render over validated PDF/image backgrounds with safe formatting,
  conditions, overflow, copies, duplex, preview marking, and exact-issue
  infrastructure. Flow-only containers/page regions are rejected; out-of-page
  geometry and rectangle overflow fail closed.
- The first visual Flow editor is complete for Owner/Admin schema-v2 drafts.
  It edits the existing validated JSON contract through the atomic revision
  service: page/theme settings, top-level ordering/removal, and common field,
  grid, section, field-plus-QR, spacer, page-break, and signature insertion.
  Preview/test-print links support iteration; advanced JSON remains the honest
  surface for page regions, detailed tables, conditions, overflow, and deep
  nested properties. Published revisions remain immutable.
- Flow v2 safe formatting, conditional presentation, and overflow policies are
  complete. Allow-listed case/date/decimal formats fail on incompatible input;
  visibility uses only registered scalar bindings and four declarative
  operators; required regulatory fields, tables, and verification must retain
  an unconditional occurrence. Wrap, bounded shrink, and explicit error
  policies replace silent clipping.
- Flow v2 configurable tables and repeating page regions are complete. Tables
  support selected payload indexes, custom labels, percentage widths,
  alignment, repeatable headings, and grid/minimal/striped variants. Bounded
  headers and footers reserve body space and repeat compact validated blocks
  on every page. Unknown indexes and region overflow fail closed.
- Flow schema-v2 containers are complete. Validated sections support plain,
  outlined, and tinted variants; proportional two-to-four-column containers
  require widths totaling 100%; field grids support one to four columns.
  Bindings and assets are discovered recursively, nesting is bounded, and page
  breaks inside containers fail closed. These are responsive flow constructs,
  not absolute PDF coordinates.
- Rich document composition has started with the Flow schema-v2 foundation.
  Existing schema-v1 layouts retain their canonical form and v1 renderer;
  schema v2 adds explicit `FLOW` mode, bounded uniform page margins, and
  allow-listed theme colors, fonts, and type sizes. `ABSOLUTE_OVERLAY` remains
  deliberately rejected until its dedicated later slice. Newly created
  starter drafts use v2; existing and imported schema-v1 revisions remain
  unchanged and supported.
- Loans document layouts now include an Owner/Admin starter guide at
  `/loans/setup/documents/guide/`, linked directly from the layout list. It
  explains the draft-to-assignment workflow, deterministic scope precedence,
  normal staff printing, immutable reprints, assets/copies, correction,
  import/export, recovery, and the remaining physical-printer acceptance gate.
  The canonical operator version lives in
  [docs/flows/loans-document-layout-operator-guide.md](flows/loans-document-layout-operator-guide.md).

## Current Shape

- Loans configurable document printing LPD0/LPD1 is complete under
  [docs/plans/loans-configurable-documents-plan.md](plans/loans-configurable-documents-plan.md).
  Accepted ADR `2026-08-06-loans-versioned-configurable-documents.md` requires
  typed projections, immutable published layout revisions, exact artifact
  retention for official issues, and fixed-renderer fallback. All six fixed
  PDF paths now read schema-versioned, allow-listed `DocumentPayload` fields
  and sections; renderers no longer read loan/event models. Existing routes,
  filenames, verification headers, eligibility, and visible content remain
  stable. Nine focused document tests pass. The full 201-test Loans command
  timed out during secondary test-database construction after 240 seconds with
  no reported assertion failure. No migration is required. LPD2, the
  database-free constrained layout schema and renderer, is now active.
- Loans configurable documents LPD2 is complete without database models.
  Schema-v1 layouts reject unknown properties, executable/model-path
  bindings, missing mandatory regulatory fields, unsupported page/copy modes,
  and absent payload fields/tables. Starter ticket/release layouts and the
  configurable ReportLab renderer support preview marking, deterministic
  payload/layout evidence hashes, long-table pagination, and single,
  original/duplicate, and duplex output. LPD2A adds tenant-bound validated
  PNG/JPEG/PDF assets, file signature/size/dimension/page checks, image/logo
  and QR blocks, PDF/image backgrounds on every duplex page, asset hashes in
  render evidence, and bundled Tamil Unicode font rendering. Missing, corrupt,
  duplicate, unsupported, and cross-workspace assets fail closed. Nineteen
  focused document tests pass. LPD3 tenant revision/assignment/issue models
  and publication services are next.
- Loans configurable documents LPD3 is complete. Tenant migrations
  `loans.0017` and `loans.0018` add workspace-owned layout identities,
  immutable draft/published/retired revisions, revision assets, deterministic
  workspace/license/series assignments, and immutable exact-byte official or
  regenerated issues. Atomic services own create, draft update, asset add,
  clone, publish, assign, resolve, retire, and issue workflows, with public
  workspace auditing. Database constraints prevent duplicate active scoped
  assignments and duplicate official issues; issue reprints are idempotent and
  regeneration links to the prior issue. Both migrations are applied across
  local schemas using `migrate_schemas`. The combined 24-test document gate
  passes. LPD4 loan-ticket pilot setup UI is next.
- Loans configurable documents LPD4 loan-ticket pilot is complete. Owner/Admin
  setup pages expose starter creation, validated schema-v1 editing, asset
  upload, preview, test print, clone, publish, scoped assignment, and
  retirement. Normal loan-ticket printing resolves
  `series -> license -> workspace -> fixed`, stores or retrieves immutable
  exact-byte official issues, and returns the issue ID. Preview output is
  non-official; the explicit fixed recovery query is administrator-only and
  audited. Tenant UI tests cover create/edit/asset/publish/assign,
  preview/download, issue/reprint, clone/retire, fixed recovery, and member
  denial. No migration is required. This pilot became the base for the now
  completed LPD5 rollout.
- Loans configurable documents LPD5 is complete. Starter creation and scoped
  rendering now cover loan tickets, repayment receipts, release memos, auction
  notices, auction recovery memos, and renewal memos. Every existing PDF route
  resolves configured layouts, creates/retrieves immutable official issues,
  exposes verification/issue headers, and preserves fixed output when no
  assignment exists. Administrator `?renderer=fixed` recovery is consistent
  and audited across document kinds. Mandatory per-kind fields remain enforced;
  release now explicitly projects its official loan number. Twenty focused
  renderer/projection tests, existing tenant-scoped essential-PDF route
  coverage, and pilot UI tests pass. No migration is required. This established
  the input to the now engineering-complete LPD6 hardening slice.
- Loans configurable documents LPD6 engineering is complete. Owner/Admin
  integrity diagnostics and tenant command `check_loan_document_integrity`
  verify canonical layout hashes, assets, exact issue bytes, scope, and issue
  lineage; `jcl1` passes the fail-on-findings gate with zero findings.
  Sanitized layout packs export only schema-v1 definitions plus validated
  hashed assets, reject unsafe or inconsistent imports, and always land as
  unassigned drafts. Automated pack round-trip and hash-drift detection tests
  pass. The operations guide is in
  [docs/implementation/loans-configurable-document-operations.md](implementation/loans-configurable-document-operations.md).
  LPD6 remains operationally open only for the real-printer A4/A5,
  simplex/duplex, regional/long content, background, QR, margin, and historical
  reprint acceptance matrix.
- Loans corrective slice E7.3A.7.3 is complete for the MVP boundary.
  Release-and-renew composite reversal now restores each source item's actual
  pre-renewal custody, so both retained and returned collateral reverse safely;
  immutable opening/closing rows remain unchanged and reversed openings stop
  contributing to successor balances. Reconciliation detects missing or
  mismatched item-principal evidence and accepts customer returns backed by a
  renewal custody event. Operational reports list release-and-renew source and
  successor loans. Release and renewal PDFs expose item principal settlement,
  retained/returned/additional movement, and successor opening allocations.
  Focused selector/document and mixed tenant workflow tests pass. No migration
  is required. Auction item-principal evidence is tracked explicitly as
  deferred slice E7.3A.8, with scope and acceptance criteria in the roadmap.
  Auction must remain outside the limited MVP pilot until that slice is
  completed.
- Loans corrective slice E7.3A.7.2 is complete: tenant migration `loans.0016`
  adds immutable item-principal closing lines for itemized full-release and
  renewal-settlement events, plus immutable opening lines for explicit
  release-and-renew successors. Closing lines freeze the item, rate, order,
  balance before, principal settled, and zero balance after. Successor opening
  lines freeze fresh item principal/rate and optional predecessor lineage;
  later repayments and accruals reconstruct their tranche bases from these
  openings without inventing a disbursal. Capitalized interest cannot be
  carried into an explicit successor until it has item attribution. Legacy
  aggregate loans remain on their compatibility path without fabricated
  lines. Focused full-release and release-and-renew coverage passes, and
  `loans.0016` is applied to all local tenant schemas.
- Release-and-renew collateral selection is implemented. The staff form now
  separates existing collateral from optional additions: selected source items
  receive explicit successor allocations and predecessor lineage, omitted
  source items return to the customer, and newly captured items enter the
  successor without fabricated lineage. Retained-plus-added allocations must
  equal successor principal. Normal draft economics independently resolve
  current metal rates and enforce per-item valuation/LTV before the atomic
  renewal commits. Source settlement and successor opening identify retained,
  returned, and additional items. Focused service/UI tests and all existing
  renewal regression tests pass. No migration was required for that slice.
- The accepted release-and-renew ADR now prohibits new same-loan partial
  collateral releases. The partial-release action is removed from the active
  loan UI; its historical URL returns an explicit Gone response and its service
  boundary rejects before mutation. Partial repayment still changes only dues,
  full release still returns all remaining collateral and closes the loan, and
  historical immutable partial-release evidence remains readable/reversible.
  Renewal now provides the replacement collateral-selection workflow.
- Loans corrective slice E7.3A.6 is complete: tenant migration `loans.0015`
  adds immutable collateral-level repayment allocation lines. Original
  principal is applied to outstanding item tranches in descending frozen
  monthly-rate order, with collateral ID as the deterministic tie-breaker;
  every line freezes its order, rate, balance before, amount applied, and
  balance after. Capitalized-interest principal remains separately classified
  and is never attributed to collateral. Later accruals reconstruct their item
  bases from the disbursal snapshot plus active allocation lines, while a
  repayment reversal restores the prior bases by excluding the reversed event
  without mutating its evidence. Missing, discontinuous, misordered, or
  unreconciled evidence fails closed. Repayment receipts expose the allocation
  trail. Migration drift and Django checks are clean, `loans.0015` is applied
  to all local tenant schemas, and the complete 192-test tenant-aware Loans
  suite passes.
- Loans corrective slice E7.3A.5 is complete: tenant migration `loans.0014`
  adds immutable collateral-level lines beneath each new itemized interest
  accrual. Every line freezes item principal base, metal rate, period fraction,
  high-precision calculation, rounded calculated interest, advance interest
  consumed, and newly due interest; header and event totals are exact sums of
  those lines. Advance interest is consumed as a per-item monetary balance, so
  partial periods cannot lose or duplicate coverage. Cash accounting creates
  no new receivable for a fully prepaid period. Accrual accounting reclassifies
  the covered amount from Unearned Revenue to INTEREST_INCOME and creates a
  borrower receivable only for the uncovered amount. Release, auction, and
  renewal catch-up accruals use the same evidence path. Legacy aggregate loans
  retain their prior calculation contract. The complete 192-test
  tenant-aware Loans suite passes; Django checks and migration drift are clean,
  and `loans.0014` is applied to all local tenant schemas.
- Loans corrective slice E7.3A.4 is complete: tenant migration `loans.0013`
  adds an immutable one-to-one disbursal snapshot linked to the exact approval,
  policy snapshot, source accounting event, and frozen item/fee evidence. New
  itemized loans reconcile gross principal exactly to net cash, advance
  interest, and deducted fees. DEA now debits gross principal, credits only net
  cash to CASH, and credits deductions to interest/fee destinations; advance
  interest uses INTEREST_INCOME for cash accounting and Unearned Revenue for
  accrual accounting. Voucher reversal therefore compensates the complete
  gross-to-net posting without mutation. Legacy allocation-null development
  approvals retain their aggregate contract without fabricated snapshots.
  Dedicated appraisal history is explicitly deferred to E7.6A; the MVP freezes
  the staff-entered appraisal value in approval/disbursal evidence. Focused
  source-to-DEA and compatibility tests pass, and `loans.0013` is applied to
  local tenant schemas. The complete 190-test Loans suite passes, followed by
  focused immutable-snapshot and accrual-basis advance-interest coverage after
  the final assertions were added. E7.3A.5 is next: item-level accrual evidence
  and advance-interest coverage without double charging.
- Loans corrective slice E7.3A.3 is complete: Owner/Admin users can configure
  effective-dated workspace defaults or license overrides for valuation/LTV,
  advance-interest periods, gold/silver monthly rates, and fees. Browser draft
  creation and editing now require collateral-level allocations, resolve
  metal-specific interest and current Rates-module valuation inputs, enforce
  item LTV server-side, derive aggregate principal/effective rate, and offer a
  no-write preview of gross principal, monthly interest, deductions, and net
  cash. Approval independently revalidates the same calculation and freezes
  item/policy provenance. Existing development/internal commands without item
  allocations remain on an explicit compatibility path and are never
  backfilled. The complete 188-test tenant-aware Loans suite passes in three
  exhaustive groups (87 + 70 + 31); Django checks and migration drift are
  clean, and no migration is required.
- Loans corrective slice E7.3A.2 is complete: tenant migration `loans.0012`
  adds effective-dated workspace configuration with optional license
  overrides for valuation/LTV/advance-interest policy, metal-specific monthly
  rates, and fixed/percentage fees. Deterministic tenant-checked resolvers use
  license-over-workspace precedence, merge fee codes, honor date ranges, and
  fail explicitly on missing required policy. Collateral rows now have
  nullable allocated-principal, frozen-rate, and rate-policy provenance fields
  so existing development history is not fabricated. Thirty-two focused
  policy, economics, core-model, registration, and draft-compatibility tests
  pass, and the migration is applied to all local tenant schemas. Runtime
  draft/disbursal behavior remained on the compatibility path until E7.3A.3.
- Loans corrective slice E7.3A.1 is complete: the accepted collateral-tranche
  ADR replaces the single-rate calculation assumption with item-allocated
  principal and metal-specific interest. A database-free calculator now
  enforces valuation-method inputs, per-item maximum LTV, one-to-twelve-or-zero
  advance-interest periods, fixed/percentage deductions, positive net cash,
  and exact gross/monthly-interest/effective-rate reconciliation. Sixteen
  focused domain and existing policy/vocabulary tests pass; no runtime model or
  migration changed. E7.3A.2 will add the complete effective-dated policy and
  collateral-allocation persistence boundary.
- Loans rewrite E7.3 is complete: immutable `PawnLoanRenewal` evidence links
  one closed source to one active, newly numbered successor for pay-and-renew
  and top-up workflows. Renewal settles interest/fees, validates current
  collateral value against the snapshotted LTV policy, preserves item-level
  lineage and vault custody, and posts only the net principal cash movement
  through DEA. Administrator-only composite reversal restores both loans and
  both custody records newest-first. The internal UI exposes renewal, lineage,
  PDF evidence, and reversal. Tenant migration `loans.0011` is ready; focused
  service, posting-contract, reconciliation, idempotency, LTV, and reversal
  coverage passes, as does the complete 170-test tenant-aware Loans suite in
  three exhaustive groups. E7.4 FundingLoan and repledging is next.
- Loans rewrite E7.2 is complete: `PawnLoanAuction` owns the overdue-loan
  auction lifecycle, source-linked notice, buyer/recovery evidence, immutable
  collateral snapshots, and custody movement to `AUCTION_DISPOSED`. Exact
  full-debt recovery posts through the Loans outbox to a dedicated DEA voucher
  rule and closes the loan; administrator-only reversal posts compensation,
  restores vault custody, and reopens it. The loan detail exposes lifecycle
  actions plus notice/recovery PDFs. Shortfall write-off and borrower-surplus
  settlement deliberately fail closed pending explicit documents. Tenant
  migration `loans.0010` is applied to local tenant schemas; the focused
  real-posting tests and complete 164-test tenant-aware Loans suite pass.
- Loans rewrite E7.1 is complete: `PawnLoanNotice` persists tenant-scoped,
  idempotent notice intent plus recipient/financial snapshots and Notify IDs for
  repayment reminders, interest due, overdue notices, and release confirmations.
  Notify v2 remains the sole owner of templates, providers, attempts, sent/failed
  state, external references, and errors; Loans derives those values for its
  detail UI and scheduler instead of storing a duplicate `notice sent` flag.
  Immediate delivery runs after commit, future work runs through tenant command
  `dispatch_pawn_loan_notices`, and failed jobs can be retried from the loan.
  Auction notices now require an E7.2 source auction. Tenant migration `loans.0009` is
  applied locally; six focused notice tests, two UI regressions, and the full
  160-test tenant-aware Loans suite pass.

Rokkad is moving toward a layered architecture:

- Domain apps own their business concepts.
- DEA owns accounting documents, vouchers, voucher lines, journal entries, posting rules, and period locking.
- Cross-app integrations should go through facades, selectors, or use-case services rather than direct model imports.
- Girvi loan operations are being moved toward command/use-case classes, with accounting effects delegated to DEA.
- Contacts are being separated from loan-specific reads through summary selectors and Girvi facades.
- UI information architecture now has a current audit and redesign plan at [docs/ui/saas_information_architecture_audit.md](ui/saas_information_architecture_audit.md), covering public/global/tenant/settings/portal separation, route risks, layout targets, flows, authorization, onboarding, roadmap, and test needs.
- Phase 2 route/template standardization has started: shared URL patterns now have explicit service/public/auth/global groups while preserving the current aggregate behavior, and templates can target `base_public.html`, `base_auth.html`, `base_global.html`, `base_tenant.html`, `base_workspace_settings.html`, and `base_customer_portal.html`.
- Phase 2.2 route intent cleanup keeps URL behavior stable while making URLConf ownership explicit: public-schema routes live through `django_project.urls`, tenant ERP prefixes are grouped in `django_project.tenant_urls.TENANT_ERP_URLPATTERNS`, and the legacy `public_urls` module stays parity-compatible.
- Phase 2.3 template layout cleanup keeps behavior stable while moving remaining clear first-party direct layout extends to intent aliases and adding guard tests for layout alias contracts.
- Phase 2.4 workspace settings layout separation keeps URLs and navigation stable while moving clear workspace-admin/settings templates to `base_workspace_settings.html` and adding no-op settings-sidebar include points for the future settings shell.
- Phase 2.5 shell render smoke tests cover representative public, auth, global, workspace settings, and tenant shell aliases with synthetic child templates before visual navigation changes.
- Phase 2.6 route/template inventory documentation captures current URLConf ownership, shell ownership, guard tests, and mixed-boundary risks in [docs/ui/route_template_inventory.md](ui/route_template_inventory.md).
- Phase 3.1 navigation and workspace switcher planning is documented in [docs/ui/navigation_workspace_switcher_plan.md](ui/navigation_workspace_switcher_plan.md), with intent tests guarding the current switcher/sidebar ownership contract before visible navigation changes.
- Phase 3.2 workspace switcher reuse is implemented: the top navbar now includes the reusable `components/navigation/workspace_switcher.html` partial in navbar mode, and authenticated global/tenant shell smoke tests cover the switcher rendering path.
- Phase 3.3 desktop workspace settings sidebar extraction is implemented: desktop workspace-admin links now live in `components/navigation/workspace_settings_sidebar.html`, while mobile management navigation remains unchanged for a later cleanup slice.
- Phase 3.4 mobile workspace settings sidebar extraction is implemented: the management offcanvas now uses the same `components/navigation/workspace_settings_sidebar.html` partial in mobile mode, removing the duplicated mobile workspace-admin links.
- Phase 3.5 account-management sidebar extraction is implemented: desktop and mobile account-management links now live in `components/navigation/account_sidebar.html`, and the management layout delegates both variants to that partial.
- Phase 3.6 workspace-manager sidebar extraction is implemented: desktop and mobile `My Workspaces` / `New Workspace` links now live in `components/navigation/workspace_manager_sidebar.html`, leaving the management layout as section shell plus partial includes.
- Phase 3.7 management shell cleanup is implemented: `layouts/management.html` has clean ASCII shell comments, stale duplicate-sidebar wording is removed, and the final management navigation partial inventory is documented.
- Phase 3.8 management-shell compatibility review is implemented: authenticated management shell smoke coverage now renders the partialized navigation and asserts key labels plus route targets still resolve.
- Phase 3.9 management shell visual-polish checklist is documented in [docs/ui/management_shell_visual_polish_checklist.md](ui/management_shell_visual_polish_checklist.md), defining compatibility and review criteria before CSS or layout-density changes.
- Phase 3.10 first management-shell visual polish pass is implemented: the management shell now uses restrained neutral styling, shared `mgmt-nav-link` classes, mobile active-state parity, and cleaner offcanvas styling without route, label, partial-ownership, or permission changes.
- Phase 3.11 rendered management-shell review is implemented: `layouts/base.html` now exposes a compatible `main_wrapper_class` block and `layouts/management.html` uses a full-width `container-fluid p-0 mt-0` wrapper so the management shell is no longer constrained by the default content container.
- Phase 3.12 reproducible management-shell visual smoke coverage is implemented in `django_project/test_management_shell_visual_smoke.py`, guarding the full-width wrapper, desktop/mobile navigation classes, active states, and control-plane route safety without adding browser dependencies.
- Phase 3.13 management-shell CSS extraction is implemented: `static/css/management.css` owns the shell visual styles, `layouts/management.html` loads it through `{% static %}`, and synthetic shell smoke tests use plain staticfiles storage to avoid stale manifest coupling.
- Phase 3.14 static asset readiness is implemented: `findstatic` resolves `css/management.css`, `collectstatic --dry-run --noinput` completes successfully, and visual smoke coverage now asserts Django staticfiles can discover the management stylesheet.
- Phase 3.15 final Phase 3 navigation/management-shell review is documented in [docs/ui/phase3_navigation_management_shell_review.md](ui/phase3_navigation_management_shell_review.md), including compatibility findings, verification commands, and the recommended phase-level commit set.
- Phase 4.1 invitation/team flow cleanup has started with documentation and guard tests only. [docs/ui/invitation_team_flow_cleanup_plan.md](ui/invitation_team_flow_cleanup_plan.md) maps incoming invitations, sent workspace invitations, and team member screens while preserving current URLs, and `django_project/test_invitation_team_flow_intent.py` guards the current route/template intent.
- Phase 4.2 route-intent cleanup keeps URL behavior stable while making org route ownership explicit: `apps.orgs.urls` now has grouped route lists for workspace manager, account invitations, workspace invitations, team members, and account profile surfaces, with tests guarding the aggregate order.
- Phase 4.3 copy/heading clarification keeps routes and form actions stable while making received invitations, sent workspace invitations, and team-member invite screens visibly distinct, with tests guarding the copy split and known mojibake cleanup.
- Phase 4.4 workspace-scoped redirect cleanup keeps old URLs working while carrying explicit workspace context through sent-invitation success/list/revoke flows and moving invite success onto the workspace settings shell.
- Phase 4.5 accept/decline characterization documents the gap between direct django-invitations accept links and the custom orgs accept flow: signal-backed membership bridging exists, but active workspace selection, orgs audit, and workspace-dashboard redirect only exist in the custom flow.
- Phase 4.6 authorization coverage adds focused tests for invite permission checks, role-grant policy, revoke denial, team remove/change-role gates, sole-owner self-leave blocking, and selected-workspace sent-invitation fallback.
- Phase 4.7 direct invitation accept adapter preserves the existing accept URL while routing authenticated matching users through the orgs control-plane accept flow; unauthenticated users still fall back to django-invitations behavior and authenticated email mismatches fail closed.
- Phase 4 final review is documented in [docs/ui/phase4_invitation_team_flow_review.md](ui/phase4_invitation_team_flow_review.md), including compatibility findings, authorization coverage, verification commands, and deferred follow-ups.
- Canonical control-plane route aliases are phase-reviewed in [docs/ui/canonical_route_aliases_phase_review.md](ui/canonical_route_aliases_phase_review.md): `django_project.shared_urlpatterns.CANONICAL_CONTROL_PLANE_URLPATTERNS` adds `/app/...` and `/workspace/<id>/settings/...` aliases while preserving existing `/orgs/...` compatibility routes. Management and workspace-settings navigation now target canonical aliases, and sent-invitation POST/back/revoke returns use the canonical settings URL while legacy route names remain active-compatible.
- Phase 5.1 authorization cleanup has started with inventory and guard tests only. [docs/ui/authorization_cleanup_inventory.md](ui/authorization_cleanup_inventory.md) maps public, global authenticated, workspace settings, tenant ERP, and future portal authorization surfaces, and `django_project/test_authorization_surface_intent.py` guards the current route-plane split, middleware membership-before-tenant-context contract, Girvi/DEA access helper contracts, and known login-only tenant app gaps before behavior changes.
- Phase 5.2 middleware canonical settings path extraction is implemented: `SecureWorkspaceMiddleware.WORKSPACE_ID_PATTERNS` now recognizes `/workspace/<id>/settings/...` aliases in addition to legacy `/orgs/workspace/<id>/...` and `/orgs/company/<id>/...` paths, with guard coverage for legacy and canonical extraction.
- Phase 5.3 middleware tenant-prefix coverage is implemented: `SecureWorkspaceMiddleware.WORKSPACE_REQUIRED_URLS` now covers every current tenant ERP prefix from `django_project.tenant_urls.TENANT_ERP_URLPATTERNS`, including `party`, `data-tools`, and `notify-v2`.
- Phase 5.4 Party access helper scaffolding is implemented: `apps.tenant_apps.party.access` now provides workspace, permission, action, decorator, and CBV mixin helpers, with focused tests covering fail-closed workspace resolution, owner/platform/member behavior, action permissions, and admin-role checks. Party views are not converted yet.
- Phase 5.5 Party read/export authorization is implemented: Party list/detail now use the Party view action guard, Party export uses the Party export action permission, and tenant UI tests cover member read access plus denied no-access/export cases.
- Phase 5.6 Party simple mutation authorization is implemented: Party create and customer-convert now use the Party create action guard, Party update uses the Party edit action guard, and tenant UI tests cover member create/update plus denied no-access create/convert/update cases.
- Phase 5.7 Party profile mutation authorization is implemented: profile photo, contact-method, and address mutations now use the Party edit action guard, with denied no-access coverage for update/remove/save/delete paths.
- Phase 5.8 Party KYC/relationship mutation authorization is implemented: identifier, document, and relationship mutations now use the Party edit action guard, with denied no-access coverage for save/delete paths.
- Phase 5.9 final Party mutation authorization is implemented: role add/end and duplicate merge now use the Party edit action guard, with denied no-access coverage for both role mutation and merge paths.
- Phase 5 Party authorization review is documented in [docs/ui/phase5_party_authorization_review.md](ui/phase5_party_authorization_review.md), confirming Party authorization coverage, compatibility findings, verification commands, and the next Product authorization cleanup direction. Broad Contact authorization cleanup is intentionally skipped because Party is replacing Contact; Contact should only receive targeted safety patches before cutover.
- Phase 5.10 Product catalog authorization is implemented: `apps.tenant_apps.product.access` now provides workspace, permission, action, decorator, and CBV mixin helpers backed by current generic data permissions, and product/product type/generated product/variant/product variant catalog views use Product action guards. Stock, pricing, image, and attribute Product surfaces remain separate follow-on slices.
- Phase 5.11 Product stock authorization is implemented: stock list/detail/search, transaction/statement lists, split/merge/delete, stock-in/stock-out, physical audit, opening balance import, and import template routes use Product action guards. `stock_select` now safely reads `?q=` when the route does not pass a positional query argument. Product pricing, image, and attribute surfaces remain separate follow-on slices.
- Phase 5.12 Product pricing/image/attribute authorization is implemented: pricing tiers, tier product prices, price overrides, product/variant image views, and attribute/attribute-value views now use Product action guards.
- Phase 5.13 Rates/Notify authorization is implemented: `apps.tenant_apps.rates.access` and `apps.tenant_apps.notify.access` now provide workspace/action guard helpers; rate/rate-source routes, legacy Notify routes, and Notify v2 user-facing batch/settings routes use action guards. Notify v2 WhatsApp Cloud webhook remains intentionally public for provider callbacks.
- Phase 5.14 SaaS IA authorization closeout is complete for the current Party, Product, Rates, Notify, and utility data-tool route groups. DEA and Girvi retain separate domain-specific permission hardening tracks because their accounting/loan semantics are broader than this UI authorization phase.
- Phase 6.1 onboarding inventory is complete for documentation and guard tests only. [docs/ui/onboarding_phase6_plan.md](ui/onboarding_phase6_plan.md) records the current user-level onboarding wizard, duplicate onboarding/orgs workspace creation paths, target workspace setup checklist, compatibility constraints, and safe implementation order.
- Phase 6.2 read-only checklist service is implemented: `apps.onboarding.services.setup_checklist` builds workspace setup checklist items from injectable metrics and best-effort tenant/org counts without mutating state or changing existing onboarding routes.
- Phase 6.3 workspace dashboard checklist surface is implemented: `apps.orgs.services.dashboard_selectors.get_workspace_dashboard_context()` now includes `setup_checklist`, and `templates/company/workspace_dashboard.html` renders the advisory workspace setup card for owner/admin dashboard users without blocking workflows.
- Phase 6.4 workspace settings setup page is implemented: canonical `workspace_settings_setup` and compatibility `workspace_setup` render the same read-only checklist in the workspace settings shell, with desktop/mobile settings-sidebar links.
- Phase 6.5 onboarding completion routing is implemented: completed onboarding start/complete/skip paths now redirect to `workspace_settings_setup` when a selected non-public workspace exists, with `workspace_list` fallback.
- Phase 6.6 onboarding workspace creation extraction is implemented: `apps.onboarding.views.onboarding_company` now delegates company/domain/Owner membership creation to `apps.orgs.services.control_plane.create_onboarding_workspace_from_form()` while preserving existing provisioning callbacks, progress, choices, audit, messages, and redirects.
- Phase 6.7 onboarding team invitation extraction is implemented: `apps.onboarding.views.onboarding_team` now delegates invitation creation/sending to `apps.orgs.services.control_plane.send_onboarding_team_invitations()` while preserving optional skip behavior, progress, messages, audit summary, and partial-failure logging.
- Phase 6.8 workspace setup state is implemented: `WorkspaceSetupState` records per-user/per-workspace dismiss and manual-complete timestamps, setup-state services expose display/mutation helpers, dashboard setup cards respect the state, and canonical/legacy setup-state POST routes are available.
- Phase 6.9 onboarding review is complete in [docs/ui/phase6_onboarding_review.md](ui/phase6_onboarding_review.md), with compatibility findings, verification commands, rollout notes, and phase-level commit guidance.
- Phase 7.1 modern fintech UI polish planning is complete for documentation and guard tests only. [docs/ui/phase7_modern_fintech_ui_polish_plan.md](ui/phase7_modern_fintech_ui_polish_plan.md) defines the public/global/tenant/settings visual targets, management/workspace setup first slice, non-negotiables, safe implementation order, and acceptance criteria. `django_project/test_phase7_ui_polish_intent.py` guards that Phase 7 starts without route, permission, middleware, schema, or onboarding behavior changes.
- Phase 7.2 workspace setup visual vocabulary is implemented: `static/css/management.css` now owns setup hero, progress, task, action, and status classes, and `templates/company/workspace_setup.html` uses them while preserving canonical setup-state forms, checklist links, settings-shell ownership, and advisory behavior.
- Phase 7.3 dashboard setup-card polish is implemented: `templates/company/workspace_dashboard.html` loads the same setup stylesheet and uses the setup hero, progress, task, action, and status classes while preserving `setup_state.should_show_dashboard_card`, the canonical setup link, the dismiss POST target, and checklist action URLs.
- Preferences visibility is clarified in the workspace settings sidebar: the canonical `workspace_settings_preferences` link is visible to `Owner`, `Admin`, and platform `Superuser` users, matching the current `workspace_settings` access boundary better than the previous Owner-only navigation.
- Centralized preferences Phase 1-4 foundation is implemented and now tracked in [docs/plans/centralized-preferences-architecture-plan.md](plans/centralized-preferences-architecture-plan.md). `apps.configuration` owns the additive workspace preference model/registry, central dynamic-preference definitions for platform/workspace/user scopes, `PreferenceService` with explicit user-override allowlisting and service-layer audit logging, admin/form/view scaffolding, and focused service tests. Existing Girvi `CompanyPreferences` behavior is preserved as a compatibility path until later module-by-module replacement.
- Centralized preferences Phase 5 Girvi runtime replacement is complete for current direct reads: Girvi loan views, disbursal forms, repayment, release lifecycle, renewal, and scheduled accrual command policy reads now go through `apps.tenant_apps.girvi.service_modules.preferences`, which delegates legacy `Loan__...` and `Interest_Rate__...` keys through `PreferenceService`. The canonical workspace settings preferences route now renders the central `workspace_preferences_registry`, the legacy Girvi preference route remains reachable, and `migrate_preferences_to_workspace --dry-run` inventories old Girvi preference rows without writes.
- Centralized preferences Phase 6/8 next slices are implemented for Girvi: snapshot tests now guard persisted loan item interest rates and disbursal deduction components against mutable preference re-reads, central lowercase `loan__...` preference definitions exist for legacy Girvi policy keys, and `migrate_preferences_to_workspace --apply` writes only those explicit legacy-to-central mappings.
- Phase 7.4 setup checklist task partial extraction is implemented: `templates/components/setup/setup_checklist_task.html` owns the repeated task/status/action markup, and both setup surfaces include it with page-specific heading/id context while preserving action URLs and setup-state behavior.
- Phase 7.5 global workspace selector polish is implemented: `templates/company/workspace_home.html` now presents a clearer workspace manager with summary tiles, active workspace state, canonical create/invitations/settings links, and preserved `workspace_select` switching plus invitation accept/decline POST behavior.

## Recently Stabilized

- PawnLoan draft detail now offers a compact collateral split workflow: select
  one or more items, choose destination Series/product/date/tenure, preview the
  destination number and both loans' economics, then confirm atomically. The
  source retains its number and at least one item; the destination consumes one
  new number, while moved item/photo identities are preserved and no accounting
  event is created. This is now the supported bulk-item workflow; the more
  complex Collateral Intake Batch UI, services, and active model state were
  removed. Migration `0052` preserves any previously captured database rows as
  inaccessible historical evidence instead of destructively dropping tables.
- PawnLoan draft correction now clearly labels existing and new collateral,
  supports adding multiple photographed collateral rows in the browser, and
  permits controlled removal of mistaken collateral and its pre-contract
  photographs/label issues while the loan remains `DRAFT`. Approval remains
  the database-enforced evidence immutability boundary.
- PawnLoan detail now provides Previous/Next controls scoped to the current
  `LoanSeries`. Navigation follows canonical loan order (`loan_date`, official
  `loan_number`, stable primary-key tie-breaker), excludes every other series,
  and renders disabled controls at either boundary.

- Loans rewrite E6.2 is complete: tenant command `compare_loan_coexistence` validates Girvi and Loans source projections against the unified coexistence contract without writes or dual ownership. It compares source and lifecycle counts, principal/interest/total balances, collateral and custody summaries, release state, and DEA-reference visibility; findings are categorized as count, lifecycle, money, custody, release, or DEA visibility with source-key evidence. Text and JSON output are supported, and `--fail-on-mismatch` makes the check usable as a pilot/deployment gate. Seven focused pure/tenant/command tests pass, including zero-mismatch and deliberately altered fixtures, and the complete then-current 143-test tenant-aware Loans suite passed; no migration was required. E6.3 subsequently completed the workspace cutover gate.
- Loans rewrite E6.3 is complete: audited central preference `loan__new_module_enabled` defaults each workspace to Girvi and can be changed only by Owner/Admin through `/loans/setup/cutover/`. When enabled, canonical navigation and known origination links route to Loans, Legacy Girvi stays visible for servicing existing Girvi-owned records, and Girvi create/preview/customer-create GET, POST, and HTMX routes enforce the boundary server-side while preserving Party handoff. Disabling restores Girvi origination without deleting or transferring PawnLoan records. Five focused tenant tests cover rollback, retained records, direct-URL enforcement, routing, Party handoff, coexistence navigation, and authorization; the complete 148-test tenant-aware Loans suite, ten central-preference tests, and 48 route/navigation intent tests pass. Django, migration-drift, compile, and whitespace checks are clean, and no migration is required. E6.4 production hardening and pilot acceptance is next.
- Loans rewrite E6.4 engineering hardening is implemented: fail-closed tenant command `check_pawn_loan_cutover_readiness` combines applied Loans migrations, numbering, failed/stale outbox, accounting setup, Loans-to-DEA reconciliation, and Girvi/Loans comparison with explicit backup, rollback, support, monitoring, permissions, and real-pilot acknowledgements. JSON evidence and `--fail-on-blocker` are supported. Local `jcl1` passes all automated gates with zero reconciliation or coexistence findings; `jsk` and `test` correctly block on missing numbering. The exercise found and fixed a DEA reconciliation interpretation bug where one-sided Party account attribution was counted again beside balanced GL lines. Five focused readiness tests, a real posting regression, and the complete expanded 153-test tenant-aware Loans suite pass. Production remains NO-GO until the target production workspace's human sign-offs are completed.
- The `jcl1` E6.4 technical pilot is complete on permanent test evidence `PL-00004`: audited feature enable/disable, draft, approval, guided borrower accounting setup, disbursal, full repayment, zero-settlement full release, collateral return, closure, balanced/source-linked DEA evidence, all three PDFs, post-pilot reconciliation, and coexistence comparison passed. A pre-pilot custom PostgreSQL backup was created and structurally listed; an isolated restore is still pending. Rollback rehearsal is engineering-complete, while backup restore, named support/monitoring ownership, target-staff permission review, and real operator acceptance remain unsigned. The feature flag was returned off when the technical pilot concluded, and production remains NO-GO with five truthful blockers.
- Loans rewrite E6.5 is active as a development cutover for `jcl1`: the audited `loan__new_module_enabled` preference is enabled, `/w/jcl1/loans/` and `/loans/internal/` resolve to Loans, direct Girvi creation redirects to Loans, and Girvi legacy list/servicing, unified coexistence, and the Loans operations console remain reachable. The post-cutover comparison has zero mismatches and all six automated readiness checks pass. The product owner explicitly waived the remaining manual readiness exercises for this disposable development workspace; that waiver does not satisfy or weaken the production E6.4 gate, which still reports five manual blockers.
- Loans rewrite E6.1 is complete: Girvi exposes source-owned GivenLoan/TakenLoan coexistence rows through its public facade, and Loans combines them with tenant-scoped PawnLoans in one immutable source-labelled portfolio contract. Rows carry product kind, lifecycle bucket, financial availability, custody summary, source identity, per-source totals, and an owner-app action name/URL; validation rejects cross-owner action namespaces. A feature-hidden read-only `/loans/internal/coexistence/` surface displays both systems without dual writes. Four focused contract/tenant/UI tests and the complete 140-test Loans suite pass; Django checks and migration drift checks are clean, and no migration is required. The full gate also made existing release/rate fixtures deterministic across calendar days.
- PawnLoan borrower accounting setup is now self-service for Owner/Admin users: the disbursement readiness panel links `BORROWER_RECEIVABLE_REQUIRED` directly to a confirmation workflow that creates or reuses the Party compatibility Customer, dedicated DEA debtor account, and active `BORROWER / BORROWER_LOAN_RECEIVABLE` mapping through existing Party and DEA service boundaries. The operation is tenant-checked, atomic, idempotent, publicly audited, and creates no voucher or journal entry. Regular workspace members receive guidance to ask an administrator. The focused 20-test readiness/service/UI gate passes and no migration is required.
- The Loans architecture and Girvi parity review is documented in [docs/apps/loans/architecture-and-girvi-parity.md](apps/loans/architecture-and-girvi-parity.md). It records the side-by-side ownership rationale, internal PawnLoan flow, improvements over Girvi, cutover requirements, essential post-MVP workflows, Girvi operational capabilities requiring carry-forward decisions, current architecture risks, and non-negotiable cutover rules. The parity register prevents missing Girvi behavior from being silently dropped.
- Loans rewrite E5.5 and the Phase 5 gate are complete: the original 134-test Loans suite passed while provisioning isolated tenant schemas and exercising real DEA posting fixtures. Its combined scenarios cover regulatory setup through closure, cash/accrual accounting, simple/compound interest, posting failure/retry, every implemented reversal class, partial/full release, expired licenses, exhausted sequences, and workspace isolation. The gate found and fixed a stale app-model registration contract and release memo generation for valid operational events with no accounting outbox. No migration was required. The PawnLoan MVP remains feature-hidden pending the rest of Phase 6.
- Loans rewrite E5.4 is complete: Owner/Admin users now have a tenant-scoped PawnLoan operations console exposing outbox status counts, controlled failed-event retry, stale processing claims, loan/release numbering readiness and exhaustion, accounting prerequisites for approved/active loans, recent reversals, and lifecycle audit evidence. The console links an in-product response guide, while the canonical operations runbook documents `migrate_schemas` deployment, hidden-MVP enablement, rollback, reconciliation, and support evidence. The focused nine-test setup/diagnostics suite and Django system check pass; no Loans migration is required. E5.5 end-to-end and tenant-isolation verification is next.
- Loans rewrite E5.3 is complete: a single PawnLoan document service and workspace-scoped routes generate the fixed loan ticket, repayment receipt, and release memo/Form H equivalent. Loan tickets are unavailable for editable drafts and render their economics and collateral from the latest immutable approval snapshot. Repayment receipts use immutable accounting-event amount splits; release memos use immutable release headers and collateral valuation snapshots. All documents include workspace/license/loan/source identities, fingerprints, accounting and reversal status where relevant, signatures, and deterministic verification IDs in both the PDF and response header. The combined 17-test renderer/tenant-route gate passes and no Loans migration is required. E5.4 operations diagnostics and runbook is next.
- Loans rewrite E5.2 is complete: tenant-scoped selectors now produce one canonical operational report bundle for active/due/overdue balances, finalized accruals, repayments, releases, collateral custody, and accounting delivery health. A DEA public read facade validates voucher existence, source linkage, journal linkage, final status, debit/credit balance, duplicate source vouchers, and economic totals without exposing DEA models to Loans. Reconciliation categorizes missing disbursal/outbox/DEA evidence, failed or stale delivery, duplicate source intent, source/outbox drift, DEA reference/link/balance mismatches, impossible custody, and closed-loan inconsistency, with loan links and controlled retry for eligible failed delivery. The feature-hidden report is linked from the internal PawnLoan list. The combined 17-test selector/UI gate passes and `makemigrations loans --check --dry-run` reports no changes. E5.3 essential PDFs is next.
- Loans rewrite E5.1 is complete: the feature-hidden PawnLoan staff UI now exposes every implemented MVP lifecycle command without admin-site or manual database intervention. State-aware detail pages recommend approval, disbursal, repayment, or accounting resolution; dedicated screens invoke service-owned disbursal, repayment, completed-period accrual, compound capitalization, full release, two-step partial-release preview/confirmation, and administrator reversal workflows. Current balances, collateral custody, accrual availability, release-readiness calculations, setup failures, and pending/failed accounting blockers are visible. Failed outbox delivery retains Owner/Admin retry, reversal controls are shown only to administrators and remain service-enforced, and the focused 10-test tenant UI suite plus Django system checks pass. E5.2 reports and reconciliation is next; production navigation remains on Girvi until the Phase 6 feature gate.
- Loans rewrite E4.4 and the Phase 4 gate are complete: release reversal now uses the existing administrator-only, reason-required, newest-first command while preserving the immutable original release. An immutable release-reversal record links the compensating release event and its paired release-day accrual reversal; custody compensation restores each item only when its current physical state still matches the original handoff. Full-release reversal reopens the loan to `ACTIVE`, partial-release reversal keeps it active, and logically reversed catch-up rows no longer shift the next accrual window. Later releases block earlier reversal until reversed first, incompatible custody and undelivered paired accounting fail before mutation, duplicate reversal is idempotent, and DEA reverses posted vouchers through its public facade. Tenant migration `loans.0008` is applied across local schemas and the connected 64-test Loans regression passes.
- Loans rewrite E4.3 is complete: the tenant-scoped partial-release command locks the active loan and all collateral, rejects full/empty/already-returned selections, requires finalized completed accrual periods, finalizes the current rounded partial period, and accepts only the E4.1-calculated minimum settlement. Fees and interest clear before the exact principal reduction needed to keep retained collateral at or below the snapshotted maximum LTV. The immutable release document snapshots selected/retained values and post-settlement LTV, only selected vault items move to customer custody, and the loan remains `ACTIVE`; the balance selector derives partial return from mixed custody rather than persisting a second lifecycle state. Duplicate requests are idempotent, a second release of the same item fails closed, zero-settlement releases remain operational-only instead of creating empty DEA vouchers, the next accrual window starts the day after the rounded release period, and later full release selects only collateral still in custody so the lifecycle cannot dead-end. No migration is required and the connected 63-test Loans regression passes.
- Loans rewrite E4.2 is complete: immutable release headers, release items, and custody-history rows preserve the full-settlement document, item valuation evidence, and every vault-to-customer handoff. The atomic full-release command locks the loan and collateral, requires all completed accrual periods to be finalized, atomically finalizes the release-day partial period using the snapshotted slab policy, reuses E4.1 valuation/readiness, requires exact canonical settlement including catch-up interest, allocates the regulatory release number, records the source event and durable DEA outbox, returns every item, and closes only after custody is complete. DEA now owns `PAWN_LOAN_RELEASE` posting with cash/accrual and capitalized-interest-principal splits aligned to repayment behavior. Duplicate request keys are idempotent, invalid accrual/accounting/custody/settlement inputs fail before mutation, tenant migration `loans.0007` is applied across local schemas, and the connected 61-test Loans regression passes.
- Loans rewrite E4.1 is complete: a tenant-scoped release-readiness selector values collateral using the snapshotted calculated-metal, latest-appraisal, or lower-of-both policy and consumes metal prices only through the Rates public facade. Each read snapshot carries net weight, purity, appraisal, as-of 24K buying rate identity/source/time, calculated value, selected policy, and final value. Partial-release readiness settles all fees and interest before calculating the principal reduction needed to keep retained collateral at or below the snapshotted maximum LTV; allowed principal rounds down to prevent fractional policy breaches. Full release requires the whole balance, already-returned collateral is excluded from retained security, lender-held or already-returned selections fail closed, and unresolved accounting or missing valuation inputs are actionable blockers. The connected 59-test Loans regression passes and no migration is required.
- Loans rewrite E3.8 and the Phase 3 gate are complete: every disbursal, repayment, accrual, or capitalization reversal is a reason-required source event with an explicit one-to-one link to its immutable original. The service authorizes only platform administrators or workspace Owner/Admin actors, rejects reversal of unresolved or unsupported events, and enforces newest-unreversed-event order. Delivery uses DEA's public facade and existing immutable voucher-reversal service, while cash-policy operational-only events reverse without fabricating vouchers. Repeated delivery and repeated same-reason commands are idempotent, conflicting reasons fail, disbursal reversal restores the loan to `APPROVED`, and canonical balances restore after compensating events. Migration `loans.0006` is applied across tenant schemas and the connected 50-test Phase 3 regression set passes.
- Loans rewrite E3.7 is complete: immutable `PawnLoanInterestAccrual` rows preserve monthly period boundaries, fractional policy, high-precision calculation base and interest, and the currency-rounded recognized amount. Preview supports full-month and cutoff-slab partial periods, while finalization accepts completed periods only and is idempotent. Compound schedules stop at snapshotted capitalization boundaries; explicit capitalization events move unpaid interest into principal before later periods use the higher base. Cash-policy accrual/capitalization remains operational-only and recognizes capitalized interest income when collected; accrual policy posts source-linked DEA receivable/income and principal/receivable reclassification vouchers. The tenant migration is applied and the connected 48-test Loans accounting regression set passes.
- Loans rewrite E3.6 is complete: the current-business-date repayment command locks the active tenant PawnLoan, allocates fees, overdue interest, current interest, then principal, rejects overpayment and invalid currency precision, and records the exact split, audit row, source event, and durable outbox atomically. A caller request key makes duplicate submission idempotent while conflicting reuse fails; unresolved accounting blocks dependent repayment. DEA's dedicated `PAWN_LOAN_REPAYMENT` rule posts cash against principal control, cash/accrual interest targets, and fee income with borrower subledger attribution. Posted effects reconcile through the canonical balance selector, and repayment never changes collateral custody.
- Loans rewrite E3.5 is complete: one tenant-scoped, event-fold selector now owns PawnLoan principal disbursed/capitalized/paid/outstanding, interest accrued/capitalized/paid/outstanding, fees assessed/paid/outstanding, total due, due date, overdue state, financial settlement, collateral-return closure readiness, and per-event posting blockers. It supports reversal inversion, ignores future-dated events for as-of reads, uses the snapshotted currency quantum, and fails closed on impossible negative or over-settled histories; simple/cash and compound/accrual cases are covered.
- Loans rewrite E3.4 is complete end to end: the service-owned PawnLoan disbursal command locks the tenant loan, rejects non-approved/expired/unready setup, persists its immutable typed policy snapshot, writes the deterministic disbursal source event and outbox, records its audit transition, and activates the loan in one transaction. Default delivery now calls DEA's public facade and dedicated `PAWN_LOAN_DISBURSAL` rule, producing a source-linked posted voucher, balanced journal, principal-control/cash GL effect, and borrower subledger attribution. Repeat submission/delivery is idempotent; unresolved delivery blocks later financial actions.
- Loans rewrite E3.3 is complete: Loans can now ask DEA's public facade for disbursal prerequisites without importing DEA models or posting code. The read-only selector returns actionable blockers for an open effective-date period, CASH funding ledger, borrower loan-receivable mapping, interest-income ledger, and a fee-income ledger only when fees apply; its enforcement helper fails closed for E3.4 while leaving draft creation unchanged.
- Loans rewrite E3.2 is complete: PawnLoan-to-DEA contracts now cover disbursal, repayment, interest accrual, capitalization, release receipt, and reversal. Each deterministic, versioned payload carries loan source identity, effective date, normalized economic values, fingerprint, and idempotency key; borrower subledger resolution is isolated behind DEA's public facade, while DEA retains all posting, voucher, journal, and period-lock responsibilities.
- Loans rewrite E3.1 is complete: tenant models now persist atomic PawnLoan accounting-event source intent and durable delivery outbox rows with deterministic idempotency keys, canonical payload fingerprints, attempts, status, errors, delivery timestamps, and DEA reference IDs. Delivery is attempted only after commit through an injected adapter seam; failures remain observable and Owner/Admin-only retry is exposed without creating DEA posting rules prematurely.
- Loans rewrite E2.7 and the Phase 2 gate are complete: row-locked services enforce approve, reopen, cancel, and unavailable-license transfer transitions. Approval creates versioned append-only snapshots of borrower/setup/economics/collateral with deterministic fingerprints; reopen and cancel require audited reasons, replacement setup consumes a new regulatory number, and internal UI actions introduce no accounting or production navigation behavior.
- Loans rewrite E2.6 is complete: feature-hidden `/loans/internal/` screens provide workspace-member list, create, edit, and detail access for new-app PawnLoan drafts. Readiness blockers direct users to Party or Owner/Admin loan setup, all writes remain service-owned and draft-only, and no primary navigation entry displaces Girvi.
- Loans rewrite E2.5 is complete: service commands create and edit PawnLoan drafts atomically from active tenant Party IDs, matching license/series setup, validated economics, and validated collateral inputs. Official numbering allocates inside the creation transaction, persistence failures roll the counter back, and durable `LoanChangeLog` rows capture creation plus before/after draft edits.
- Loans rewrite E2.4 is complete: Owner/Admin users can manage regulatory licenses and bounded loan/release series from tenant-only `/loans/setup/` screens without admin-site access. The UI exposes active, inactive, expired, exhausted, and ready states plus non-consuming next-number previews; workspace-filtered lookups and middleware authorization fail closed.
- Loans rewrite E2.3 is complete: pawn-loan and release numbering have non-consuming previews and atomic PostgreSQL row-locked allocation, committed allocations never recycle, sequence exhaustion fails closed at the configured maximum, and a two-connection concurrency test proves unique serialization. The pawn draft service will call the dedicated allocation entry point during E2.5.
- Loans rewrite E2.2 is complete: tenant-only services own license and series setup, expired or inactive licenses remain readable but fail issuance eligibility, multiple active licenses are supported per workspace, and guarded sequence configuration changes are recorded in the public workspace audit trail.
- Girvi audit follow-up Phases 1-6 are complete. A tenant-schema integration test now covers Party bridge/collateral creation through real DEA disbursal, repayment, release accrual, custody, snapshot, receipt, and closure; repayment repeated-key/different-key behavior is covered; settlement failures fail closed instead of silently becoming zero; selector-compatibility releases are reconciliation-visible; and the consolidated stabilization suite passes 74 tests.
- Girvi release custody persistence now uses an explicit custody-only save path. Normal collateral edits remain blocked after approval, while release/repledge/return custody transitions can persist their owned fields without being mistaken for general loan-item edits.
- Girvi loan ID preview/allocation now treats the sequence row as a floor, not unquestioned truth: stale `GirviNumberSequence.next_number` values are skipped against existing GivenLoan/TakenLoan/Release IDs, and the create-form series AJAX endpoint renders the create-form loan ID field so selected series show the next available ID instead of the previous allocated ID.
- A client/investor-friendly non-technical BRD is now documented in [docs/product/business-requirements-document-client-investor.md](product/business-requirements-document-client-investor.md), summarizing product vision, business outcomes, scope, value proposition, and investment rationale from the implemented platform baseline.
- A BRD implementation gap report and phased delivery plan is now documented in [docs/plans/brd-gap-report-phased-delivery-plan.md](plans/brd-gap-report-phased-delivery-plan.md), mapping implemented-versus-missing capability themes and defining Phase 1-4 execution outcomes focused on tenant safety, workspace identity decoupling, canonical workflow consolidation, onboarding acceleration, and scale readiness.
- A reverse-engineered business requirements baseline is now documented in [docs/product/business-requirements-document-reverse-engineered.md](product/business-requirements-document-reverse-engineered.md), capturing implemented scope, requirement IDs, acceptance criteria, non-functional constraints, and tenancy/accounting/commodity follow-up risks from the current codebase state.
- A focused `django-tenants` usage audit is documented in [docs/implementation/django-tenants-architecture-audit.md](implementation/django-tenants-architecture-audit.md). The implementation is broadly healthy and should continue with `django-tenants` for now, but the next safety hardening should address hard-delete configuration, tenant context for Celery/background work, `import_statement_items` schema-name misuse, and consistent onboarding schema-name validation.
- The unused, non-installed `apps/tenant_apps/Chitfund` app was removed after confirming it had no external runtime references.
- Girvi license expiry report no longer uses the unsupported Django template `abs` filter; the view now supplies display-ready expiry day values, including zero-day expiries.
- Workspace dashboard/setup checklist Parties actions now reverse through the workspace slug Party alias when schema context is available, preventing `NoReverseMatch` for stale unnamespaced `party_list` links on `/orgs/workspace/<id>/dashboard/`.
- Girvi release-state detection now verifies cached reverse `Release` relations against the database before treating a loan as released, preventing false "already released" errors after rolled-back release attempts on settled loans in Closure Pending.
- Girvi release execution now moves in-vault collateral to `WITH_CUSTOMER` before persisting the `Release` row, preventing item-level false failures where an in-vault item became non-releasable the moment the release record was saved.
- Girvi release lifecycle results now include explicit stage outcomes (`readiness_checked`, `accrual_catchup`, `custody_transferred`, `release_saved`, `closure_completed`, `posting_completed`) plus stage-scoped warnings/errors and `failed_stage`, so partial failures are diagnosable without parsing free-form messages.
- Girvi release-triggered accrual catch-up now has an explicit fail policy preference (`Loan__Release_Fail_Closed_On_Accrual_Error`): compatibility mode continues release with warnings on accrual failure, while fail-closed mode blocks release before custody/release persistence.
- Contact stale loan references were removed or routed behind selectors/facades.
- Girvi dashboard and loan list now target `GivenLoan` / `TakenLoan` instead of legacy loan models.
- DEA facade boundaries were split internally and protected with architecture import tests.
- Girvi introduced a facade for cross-app reads.
- Rates are exposed in navigation/dashboard paths, with visible rate-source setup.
- Girvi disbursal can self-heal missing voucher types and ensure customer accounts before posting.
- Dashboard numeric values such as pure weight and current value are formatted to two decimal places.
- Agent-facing documentation was split by purpose: root `AGENTS.md` now contains operating rules, `docs/AGENT_MEMORY.md` contains durable project context, and `docs/constitution.md` contains non-negotiable accounting principles.
- Orgs now has a centralized role policy for membership and invitation changes, named integrity constraints for workspace membership/invitations, corrected sidebar permission codenames, and dashboard reads routed through app facades/selectors.
- Party has been accepted as the long-term external entity model. `contact.Customer` remains the compatibility model until a phased bridge and migration are implemented.
- Party Phase 1 is complete: the tenant app skeleton, initial model layer, admin registration, selectors/facade, migration, and model tests were added without changing existing Contact/Girvi/DEA behavior.
- Party Phase 2 is complete: canonical role seed data, an idempotent `seed_party_roles` command, tenant default seeding integration, and seed tests were added. Existing tenant schemas were seeded with the canonical roles.
- Party Phase 3 is complete: the nullable `Customer.party` compatibility bridge, idempotent customer-to-party backfill service, command, tests, and existing tenant backfill were completed.
- Party Phase 4 is complete: DEA now has party-role account mappings, account resolution through the public facade, support for multiple DEA accounts per bridged customer/party, and a `Customer.account` read compatibility alias.
- Party Phase 5 is complete: current Girvi borrower/lender disbursal, repayment, release, auction, sale, and legacy repayment posting paths resolve subledger accounts by role and purpose through the DEA resolver instead of reading `Customer.account` directly.
- Party Phase 6 is complete: DEA sales and purchase invoice posting rules resolve customer receivable and supplier payable accounts through party-aware role/purpose resolution, and those rules now emit the current posting bundle shape.
- Party Phase 7 is complete: the tenant Party UI now exposes list/search/filter, create/edit, detail tabs, role add/end, read-only contact/address/KYC data, DEA party account mapping visibility, and linked legacy customer activity for loans, sales, and purchases.
- Party Phase 7.1 is complete: Party detail now supports profile photo upload/removal plus inline add/edit/delete for contact methods, addresses, identifiers, and documents, with primary contact sync to Party summary fields.
- Party Phase 7.2 is complete: Party contact forms now validate phone/mobile/WhatsApp values, normalize phone numbers to E.164, validate email and website contact values, and expose Party relationship add/edit/delete on the Party detail page.
- Party Phase 7.3 is complete: Party now captures textual identity relations such as `S/o`, `D/o`, `C/o`, and `W/o` with a related person name, including bridge mapping from `Customer.relatedas` / `relatedto`.
- Party Phase 7.4 is complete: Party profile photos can now be captured from a device camera or uploaded from a file on the Party detail page.
- Party Phase 8 is complete: Party UI now supports converting unlinked legacy customers and merging duplicate parties with explicit guardrails for legacy customer links, identifiers, and DEA account mappings.
- Party Phase 9 is complete for the current prioritized scope: Girvi loans, DEA sales/purchase invoice vouchers, legacy notifications, and Notify v2 recipients now have nullable Party shadow FKs with bridge backfills or save-time sync. Approval is intentionally skipped until approval workflows become a priority again.
- Party Phase 10 read-only portal MVP is implemented. `PartyPortalAccess` links an authenticated user to a tenant Party without workspace membership, tenant `/portal/...` routes are live for dashboard, loans, invoices, payments, documents, and statements, public `/portal/...` remains absent, and selectors filter by the resolved active Party grant.
- Party Phase 10 portal hardening now includes real tenant selector/render coverage for Party-scoped Girvi loans, invoices, payments, statements, and portal page rendering. Cross-party loan/invoice/payment rows are denied by selector scope, and portal invoice/payment templates render amount plus currency explicitly instead of implicit `Money` formatting.
- Experimental operational `sales`, `purchase`, and `approval` tenant apps were removed from runtime on 2026-06-19. DEA `SalesInvoiceVoucher` and `PurchaseInvoiceVoucher` remain in place for monetary accounting while commerce/procurement is redesigned around commodity, inventory, and settlement.
- Cleanup validation passed on 2026-06-19 against a fresh isolated validation database: `migrate_schemas --shared`, tenant schema creation/migration, tenant default seeding, Party operational-link tests, product inventory/pricing tests, and current DEA party sales/purchase posting tests.
- Runtime role seed definitions no longer create or assign the stale experimental sales/purchase permission codenames; DEA invoice vouchers remain covered by DEA permissions.
- Girvi lifecycle language has been canonicalized in runtime code: `GivenLoan` now uses the canonical lifecycle flow, legacy transition names are aliases, and `TakenLoan` has a smaller dedicated lifecycle.
- Girvi app internals were documented under `docs/apps/girvi/`, covering architecture, models, backend workflows, userflows, and refactor priorities.
- Onboarding workspace creation no longer wraps tenant schema provisioning/migration in an outer application transaction, avoiding PostgreSQL pending-trigger failures when DEA seed migrations are followed by `ALTER TABLE` migrations such as `dea.0015`.
- Generic tenant model import/export moved out of Contact into tenant utility data tools, with sidebar visibility for Owner/Admin users and compatibility redirects from the old Contact URLs.
- Party creation now auto-generates tenant-local sequential `P-000001` style party codes when no code is supplied, while preserving manual/imported codes.
- Girvi given-loan creation is now Party-first: the create form selects an active Party, auto-bridges that Party to a compatibility `Customer` on save when needed, stores `GivenLoan.borrower_party`, and keeps the legacy `borrower` field populated for compatibility.
- Party list now supports filtered CSV/XLSX export for Owner/Admin users, using a flat Party export with active roles and compatibility customer linkage.
- Girvi cleanup P1 is complete: broken legacy reminder Celery tasks now fail closed as disabled, item-type averages no longer query the removed `loan_type` field, interest-accrual command output is ASCII-safe for Windows consoles, repledge creation now resolves an active loan series before creating `TakenLoan`, custody runtime helpers no longer import legacy `models.loan` or assume `loan.customer`, custody FKs now have a guarded migration to `TakenLoan`, `RepledgedLoanItem` mutation routes are read-only legacy surfaces, custody return/release behavior has focused guardrail coverage, TakenLoan direct plus queryset amount/weight/value/interest reads now use `RepledgeHistory`, and refactored interest metrics no longer shadow read-only model properties.
- Girvi cleanup P2 is complete: transition aliases remain accepted, primary state/UI/form transition registries now contain canonical entries while legacy-only metadata is isolated in explicit compatibility registries, TakenLoan transition metadata covers activate/settlement states, active list/detail/transition surfaces display canonical lifecycle labels instead of raw legacy statuses, and flow-derived tests verify transition registry metadata against `flows.py`.
- Girvi cleanup P3 is complete for current refactored runtime paths: synchronous Girvi payment, loan posting, accrual posting, repayment view posting, loan journal reads, model payment helper voucher creation, and dashboard payment counts now go through `apps.tenant_apps.girvi.integrations.dea_adapter`, with compatibility wrappers retained for old import/method surfaces.
- Girvi cleanup P4 has started: `loan_detail` display metrics, storage position lookup, interest reporting, and release CTA metadata now come from the detail read-model selector instead of being calculated directly in the view.
- Girvi repayment view orchestration is now service-backed: GivenLoan receipt catch-up accrual, repayment payload shaping, DEA posting delegation, and TakenLoan repayment posting live in `service_modules.repayment`, leaving `loanpayment.py` as form/message/redirect coordination.
- Girvi cleanup P4 is complete: bulk merge/delete selection parsing, guard validation, merge orchestration, and delete orchestration now live in `service_modules.bulk_operations`, leaving `views.loan` as message/redirect coordination for those actions.
- Girvi cleanup P5 has started: deprecated `Loan` / `LoanPayment` are no longer exported from `apps.tenant_apps.girvi.models`; explicit historical access now goes through `apps.tenant_apps.girvi.models.legacy`, stale management command imports were moved to `GivenLoan` where appropriate, legacy payment import/export is labelled as `LegacyLoanPaymentResource`, and architecture tests guard against broad legacy imports.
- Girvi cleanup P5 command-policy pass is complete: legacy manual `do` is runtime-disabled, legacy `missingcol` is opt-in only via `GIRVI_ENABLE_LEGACY_IMPORT_COMMANDS=1`, and guardrail tests enforce both behaviors.
- Girvi cleanup P6 planning has concrete route inventory/matrix coverage in `docs/apps/girvi/url-compatibility-matrix.md`, including canonical-vs-alias mapping for duplicate route names/paths before alias removal.
- Girvi cleanup P6 internal reverse canonicalization has started: base navigation template links now use canonical `girvi_*` storage-box route names, while alias routes remain in place for compatibility.
- Girvi cleanup P6 route canonicalization freeze is now implemented: `apps.tenant_apps.girvi.urls` publishes `GIRVI_CANONICAL_ROUTE_NAMES` and `GIRVI_FROZEN_ALIAS_ROUTE_NAMES`, duplicate paths list canonical names first with explicit alias-freeze comments, and `apps.tenant_apps.girvi.tests.test_url_canonicalization_intent` guards canonical reverse parity, alias compatibility, and canonical resolver precedence.
- Girvi cleanup P7 scaffolding has started: a tenant outbox model/migration for posting events, outbox enqueue helper, and draft Girvi posting event contract payload helpers were added without changing current synchronous posting execution paths.
- Girvi cleanup P7 execution is currently paused by project decision; existing synchronous Girvi to DEA posting remains the runtime path while outbox scaffolding stays in place.
- Girvi Phase 1 safety work has started from `docs/roadmaps/girvi_refactor_plan.md`: release creation now fails closed when collateral custody cannot be moved to the customer, preventing closure transitions and release accounting from continuing after item-level custody errors.
- Girvi Phase 1 repayment safety now fails closed for GivenLoan and TakenLoan repayment posting paths: payment creation and DEA posting are wrapped in atomic boundaries where the service creates the payment, and posting failures surface as errors instead of "payment saved but accounting failed" warnings.
- Girvi Phase 1 safety pass completed the safe code slices from the roadmap: settlement balance is centralized in selectors, repayment overpayment/interest over-allocation is blocked in forms and services, release/closure checks use the settlement read model, loan items are immutable after the loan leaves editable states, overdue/cure/renewal/auction transitions have stronger preconditions, renewal disbursal posting now fails closed, repayment duplicate reference numbers are idempotent, and loan ID generation scans GivenLoan and TakenLoan sequences under the locked series.
- Girvi Phase 1 interest policy is now explicit: `InterestCalculationService` codifies a minimum first-month charge for any positive duration, treats partial months as full months, applies a 3-calendar-day grace window before adding an extra partial-month charge, and routes refactored plus legacy loan interest due helpers through that shared calculation.
- Girvi Phase 1 tenant-access route coverage is closed for Phase 1.5: `views.access.assert_girvi_workspace_access` now fails closed when a Girvi request has no tenant workspace or the user is not a member, and dashboard, main loan, transition/detail tabs, repayment, release, notices, reports, prints/PDF exports, custody, statement, and template/document routes use that guard.
- Girvi Phase 1 overdue/NPA policy is explicit: overdue is allowed when maturity date is before today or settlement amount exceeds current collateral value; NPA is allowed only when settlement amount exceeds current collateral value; new Girvi auction notices use `notify_v2`, and notice failures do not block lifecycle transitions but are recorded in `LoanChangeLog`.
- Girvi Phase 1 auction/sale recovery guardrails are complete for MVP safety: auction/sale recovery amounts must be present and positive, close-after-auction requires the settlement balance to be clear, and direct write-off now fails closed until an explicit settlement adjustment document and DEA posting path exists.
- Girvi Phase 1 duplicate-submit and immutability guardrails are closed for MVP safety: manual/imported loan IDs validate across GivenLoan and TakenLoan tables, release duplicate submits are rejected before custody/accounting side effects, and `policies.py` blocks direct GivenLoan header edits once the loan leaves editable pre-disbursal states.
- Girvi Phase 2 has started: GivenLoan and TakenLoan repayment screens now render a settlement preview showing principal due, interest due, paid amount, outstanding amount, and suggested exact-payment split from the shared repayment read model.
- Girvi Phase 2 task 17 release checklist is now implemented: release entry paths now use a shared readiness checklist that blocks release when settlement cannot be calculated or collateral is still with lenders, while collectable final dues are handled by the release submit receipt; the custody check route renders a checklist-first screen under `templates/girvi/release/release_custody_check.html`, and integration tests cover blocked-vs-ready release create behavior.
- Girvi Phase 2 task 18 overdue/NPA operational queue is now implemented: dashboard context now includes a selector-backed queue for due-today, overdue transition candidates, NPA candidates, cure candidates, and notice candidates, with action links guarded by runtime transition readiness and draft-notice presence.
- Girvi Phase 2 task 19 loan/accounting reconciliation report is now implemented: a selector-backed report route and template list loans with missing disbursal vouchers, failed payment posting rows, release-without-voucher mismatches, and posted-voucher/state mismatches, with dashboard navigation and focused selector/view tests.
- Girvi Phase 2 task 20 customer/Party loan history view is now implemented: Party detail loans tab now uses Girvi facade read models to show active and closed Given/Taken loans, payment and notice counts, and collateral summaries for Party-linked and compatibility-bridged customer records, with focused Party UI coverage.
- Girvi Phase 2 task 21 permission hardening is now implemented: Girvi workspace access now supports explicit permission gates for create/edit/delete, transition/disbursal, repayment, release workflows, and report endpoints via shared access decorators/mixins, with focused permission-denial tests to prevent login-only operational access.
- Girvi Phase 2 task 22 notice-flow standardization is now implemented: both legacy and v2 Girvi bulk notice actions now converge on a single notify_v2 batch dispatch path that records intent/events, keeps loan linkage in selection snapshots/payloads, surfaces delivery status through notify_v2 job states, and preserves legacy URL compatibility as an alias.
- Girvi Phase 2 task 23 document/PDF standardization is now implemented for MVP document surfaces: `GirviDocumentService` is the shared entry point for loan ticket, release Form H, and repayment receipt PDFs; existing loan/release routes now call the shared service; and loan-detail payment rows now expose receipt printing through a permission-gated Girvi endpoint.
- Girvi Phase 2 task 24 safe operations tooling is now implemented: a permission-gated Operations Console report route exposes payment posting status, outbox status, controlled retry for failed/dead-letter Girvi posting outbox events, setup health summaries (series/rates), and recent loan audit events, with focused permission and retry behavior tests.
- Girvi Phase 2 task 25 essential reports are now implemented: a permission-gated Operational Controls report consolidates outstanding aging buckets, collateral custody distribution, release-ready checks, and rate exceptions alongside the existing reconciliation report surface.
- Girvi Phase 3 task 26 policy layer centralization is now implemented for core action guardrails: `policies.py` now provides release eligibility, repayment-permission, and transition-readiness checks, and release/repayment/transition entry views call these shared policies with focused policy and permission-smoke coverage.
- Girvi Phase 3 task 27 is complete: release, repayment, transition, custody, repledge, and transition-side-effect view orchestration now runs through workflow service modules; loan create/update preview-input parsing and create/update command/persistence helpers are centralized in `service_modules/loan_workflow.py`, leaving view paths focused on request parsing, permission checks, user messages, and redirects/responses.
- Girvi Phase 3 task 28 is complete: form-side workflow/business checks are centralized in validation services (`release_form_validation`, `repayment_form_validation`, `loan_item_form_validation`, `loan_form_validation`), and side-effectful storage-box save behavior remains in `storagebox_workflow`, keeping forms focused on input shape/binding and delegated validation.
- Girvi Phase 3 task 29 is complete: operations-console report summary queries are exposed through selector read model `build_operations_console_read_model`, repledge-history report query/filter/count payload is exposed through selector read model `build_repledge_history_read_model`, item-custody API JSON payload is exposed through selector read model `build_item_custody_status_payload`, dashboard aggregate/count context is exposed through selector read model `build_girvi_dashboard_read_model`, and reconciliation/operational-controls report context shaping is exposed through selector context helpers, with views consuming selector payloads instead of assembling data inline.
- Girvi Phase 3 task 30 is complete for current MVP model-simplification scope: statement verification missing/released/summary reads are selector-owned (`get_statement_missing_loans`, `get_statement_released_items_present`, `build_statement_verification_summary`, `build_statement_detail_read_model`) with model/view delegation, and high-usage GivenLoan/TakenLoan read-only aggregates plus shared payment/interest accrual calculations are selector-owned (with compatibility wrappers retained in `models/loan_refactored.py`).
- Girvi Phase 3 task 31 is complete: runtime `LoanChangeLog` consumers import from package-level models instead of `models.loan`, migration compatibility in `models/loan_refactored.py` uses explicit `models.legacy`, architecture guard tests restrict direct `models.loan`/`models.legacy` imports to explicit compatibility files, command-boundary tests ensure only `missingcol.py` imports deprecated legacy loan models, runtime modules are guarded from importing legacy manual commands (`do`, `missingcol`), and legacy command lifecycle policy is documented in `docs/implementation/girvi-legacy-command-lifecycle.md`.
- Girvi Phase 3 task 34 is complete: Girvi runtime notice/event/channel mapping now goes through `integrations/notification_adapter` (including transition command, notice views, print notice dispatch, dashboard/operational draft-notice checks), loan create preview customer lookup now goes through Contact facade queryset, and AST guardrails enforce that key boundary modules (`selectors.py`, `views/loan.py`, `views/notice.py`, `views/prints.py`, `transitions/commands.py`) do not directly import notify/contact model modules.
- Girvi Phase 4 task 35 is complete: loan create/update now use simple full-page workspace forms instead of modal launchers, new-loan creation keeps terms and initial collateral in one page flow, and the create preview shows current collateral value, pure weight, LTV, and missing-rate warnings.
- Girvi Phase 4 task 36 is complete: loan detail now has a selector-backed action-readiness panel that highlights the primary next action, settlement status, collateral adequacy, accounting journal presence, and timeline event count above the existing transition buttons and detail tabs.
- Girvi Phase 4 task 37 is complete: repayment capture now offers exact-settlement, interest-only, and principal-only presets from the shared repayment preview, states that saving posts to accounting, and repayment success messages report total, principal, interest, and remaining outstanding.
- Girvi Phase 4 task 39 is complete: release form and blocked custody-check pages now use `ReleaseWorkflowService.build_flow_context` and a shared release readiness panel showing settlement, custody, recipient, Form H document expectation, and accounting-posting expectation before submit.
- Girvi disbursal policy first slice is complete: disbursement transition form now supports explicit preview-only `upfront_interest_deduction` and `document_charge` components with company/global policy enforcement (`Loan__Disbursal_Deductions_Enabled`, `Loan__Minimum_Document_Charge`, existing `Loan__Interest_Deduction`). Validation blocks deductions when disabled, enforces minimum document charge when enabled, and shows gross/deduction/net payout preview in the transition UI while keeping current disbursal posting unchanged.
- Girvi disbursal accounting second slice is complete: GivenLoan now persists disbursal deduction components (`disbursal_upfront_interest_deduction`, `disbursal_document_charge`) at transition time, disbursal vouchers now post explicit components (gross principal, upfront interest deduction, document charge, net cash payout), and DEA `GIVENLOAN_PAYMENT` posting now credits net cash plus separate deduction income lines while keeping principal subledger attribution intact. Economic payload contract fields now include these disbursal components.
- Girvi Phase 4 task 42 is complete: Party detail loan history now exposes a richer Girvi facade read model with active/closed loans, outstanding split, payment totals, notice counts, collateral totals, repayment shortcuts, and release/Form H document links.
- Girvi Phase 5 accounting-readiness is complete for current scope: `integrations.dea_adapter` now owns the versioned posting event contract, idempotency key construction, source-document economic payload extraction, posting-status read model, and reversal delegation; architecture tests block runtime direct DEA imports outside the adapter/compatibility seam.
- DEA commodity-accounting refactor Phase 1 has started: financial posting characterization tests now cover manual journal, sales invoice, and purchase invoice posting through `DjangoPostingEngine`, asserting posted voucher status/fingerprint, financial journal period assignment, balanced ledger transactions, and monetary subledger account rows before commodity model changes begin.
- DEA Phase 1 balance/data-safety coverage now also characterizes ledger-vs-subledger semantics, documents the current `ledger_balances` behavior that merges GL and account transaction effects, and adds a read-only `audit_dea_currency_codes` command with tests to flag suspicious metal-like values in DEA money currency columns.
- DEA Phase 1 trial balance guardrails now assert financial debit/credit totals and base-currency reporting for non-base monetary postings. `ReportsService.trial_balance()` now computes debit and credit sides from base-currency ledger transaction totals instead of misclassifying debited asset balances as credits.
- DEA Phase 1 monetary currency guardrail design is documented in `docs/implementation/dea-monetary-currency-guardrails.md`, covering allowed monetary code policy, disallowed metal-like codes, data-audit steps, and staged future enforcement points for posting validation, currency configuration, exchange rates, forms, opening balances, materialization, and reports.
- DEA Phase 2 has started: `docs/adr/2026-06-24-dea-document-voucher-journal-lifecycle.md` now defines the business document, voucher, journal entry, reversal/correction, fingerprint, and race-safety lifecycle contract. Posted immutability coverage now verifies `JournalEntry`, `VoucherLine`, `LedgerTransaction`, and `AccountTransaction` supported update/delete paths, and ledger/account transaction models reject direct mutation under posted journal entries.
- DEA Phase 2 idempotency coverage now protects the current service/engine path: posting the same voucher twice returns the existing journal entry, reposting the same business document payload returns the existing voucher/journal entry, changed economic payloads reverse the previous voucher and post a corrected voucher, and service-returned vouchers are refreshed after engine posting. The posting engine fingerprint now uses stable economic payloads instead of voucher row ids/timestamps.
- DEA Phase 2 canonical posting path is documented in `docs/implementation/dea-canonical-posting-path.md`: `create_and_post_voucher_for_doc()` / `PostVoucherCommand` / `DjangoPostingEngine` are the authoritative posting path, while direct materialization in `views/voucher.py` and `posting/legacy_direct_write_engine.py` are legacy pending characterization and replacement.
- DEA Phase 2 reversal/correction service contract is documented in `docs/implementation/dea-reversal-correction-contract.md`: target `services/reversal.py` APIs, reversal/correction semantics, period policy, idempotency rules, audit payload expectations, current legacy paths, and future commodity sidecar reversal requirements are defined before implementation.
- DEA Phase 2 reversal implementation has started: `apps/tenant_apps/dea/services/reversal.py` now provides `reverse_posted_voucher()` with typed result/errors, transaction wrapping, period validation, audit logging, ledger/account reversal row creation, and duplicate-reversal idempotency. `DjangoPostingEngine.reverse_voucher()` delegates to this service for compatibility, and focused tests cover manual reversal, duplicate reversal, account-side flipping, and draft rejection.
- DEA Phase 2 reversal caller migration has started: `apps/tenant_apps/dea/facades/payments.py::reverse_payment_by_marker()` now calls `reverse_posted_voucher()` directly and focused payment facade tests verify successful marker reversal plus missing-accounting-voucher errors.
- DEA Phase 2 reversal caller migration now includes the voucher UI route: `apps/tenant_apps/dea/views/voucher.py::reverse_voucher()` delegates to `reverse_posted_voucher()` instead of direct reversal materialization, with route-level tests covering posted-voucher reversal and draft rejection.
- DEA Phase 2 canonical posting caller migration now includes the voucher UI post route: `apps/tenant_apps/dea/views/voucher.py::post_voucher()` delegates to `PostVoucherCommand(DjangoPostingEngine())`, and manual stored-line vouchers with no registered posting rule are materialized through `PostVoucherCommand` using `materialize_journal_from_voucher_lines()` rather than view-owned posting logic.
- DEA Phase 3 has started: `docs/adr/2026-06-24-dea-commodity-accounting-layer.md` accepts a side-by-side commodity accounting layer for metals, commodity accounts, immutable movements, exposure, rate fixing, and reporting-first valuation while keeping financial currency accounting and trial balance monetary only.
- DEA Phase 3 schema planning is complete: `docs/implementation/dea-commodity-model-schema.md` defines the proposed commodity model fields, constraints, indexes, lifecycle/immutability rules, tenant rollout notes, and required tests. It is being kept current as small model slices land.
- DEA Phase 3 first model slice is complete: `Commodity` and `CommodityAccount` were added with tenant migration `dea.0033`, admin registration, model exports, monetary-code guard validation, party-obligation account validation, and focused tests. Commodity movements, exposure, rate fixing, posting services, reports, and UI remain intentionally deferred.
- DEA Phase 3 default commodity setup is complete: `seed_default_commodities()` and `seed_dea_commodities` create/repair tenant-local `GOLD` and `SILVER` commodity masters idempotently.
- DEA Phase 3 commodity movement model is complete: `CommodityMovement` was added with tenant migration `dea.0034`, read-only admin diagnostics, source/voucher links, explicit commodity quantity fields, monetary valuation currency validation, idempotency/reversal links, and immutability guardrails.
- DEA Phase 3 exposure/rate-fixing model foundations are complete: `ExposureLine`, `RateFixing`, and `RateFixingAllocation` were added with tenant migration `dea.0035`, admin diagnostics, quantity/status/currency validation, fixing allocation guardrails, and focused tests.
- DEA Phase 3 commodity posting service skeleton is complete: `apps.tenant_apps.dea.services.commodity_posting` creates idempotent `CommodityMovement` and `ExposureLine` records from structured payloads with deterministic source/economic-payload keys. It is intentionally side-by-side and not integrated with financial posting, reports, workflows, or UI.
- DEA Phase 3 commodity position selectors are complete: `apps.tenant_apps.dea.selectors.commodity` computes movement-derived metal balances by commodity account, party, location, fixed status, and as-of date with reversal offsets and decimal quantity fields.
- DEA Phase 3 MVP commodity valuation policy is documented in `docs/implementation/dea-commodity-valuation-policy.md`: valuation remains reporting-only, uses rates as market inputs, defaults to INR, exposes missing-rate status instead of silent zero values, and defers `ValuationSnapshot`, unrealized gain/loss, and financial journal effects.
- DEA Phase 3 valuation service/read-model foundation is complete: `rates.facade.get_latest_commodity_valuation_rate()` and `dea.services.valuation` value commodity position rows and exposure lines using rates, buying/selling side policy, explicit missing/unsupported statuses, and no financial transaction side effects. Focused commodity valuation tests pass; reports, UI, snapshots, and unrealized gain/loss accounting remain deferred.
- DEA Phase 4 fixed purchase backend MVP slice is complete: `dea.services.fixed_purchase.post_fixed_purchase()` creates INR-only financial voucher lines through `PostVoucherCommand(DjangoPostingEngine())` and a side-by-side fixed `CommodityMovement` in one atomic service path, with tests for ledger/account effects, commodity movement linkage, idempotency, changed-payload rejection until correction/reversal, non-INR rejection, and rollback on commodity validation failure. UI, taxes, FX purchase policy, operational purchase document modeling, and commodity reversal sidecar remain deferred. The next recommended DEA slice is unfixed purchase backend MVP: commodity movement plus open purchase exposure without false final monetary payable.
- DEA Phase 4 unfixed purchase backend MVP slice is complete: `dea.services.unfixed_purchase.post_unfixed_purchase()` creates a posted commodity-intent voucher, `CommodityMovement`, and open purchase `ExposureLine` without creating financial journal, ledger, account, or voucher-line rows before rate fixing. The service validates period openness, is idempotent by source plus economic payload, rejects changed payloads for the same source until correction/reversal exists, and rolls back completely on commodity/exposure validation failure. The next recommended DEA slice is rate fixing backend MVP: close/reduce purchase exposure and create monetary payable through financial posting.
- DEA Phase 4 rate fixing backend MVP slice is complete for purchase and sale: `dea.services.rate_fixing.post_purchase_rate_fixing()` fixes purchase exposures into supplier monetary payable, while `post_sale_rate_fixing()` fixes sale exposures into customer receivable/revenue. Both paths record `RateFixing` and `RateFixingAllocation`, post through financial voucher lines and `PostVoucherCommand(DjangoPostingEngine())`, and reduce/close exposure atomically. Tests cover full/partial fixing, idempotency, account/ledger effects, over-fixing rejection, closed-period rejection, and no partial state on failure.
- DEA Phase 4 fixed sale backend MVP slice is complete: `dea.services.fixed_sale.post_fixed_sale()` creates INR-only customer receivable/revenue financial effects through `PostVoucherCommand(DjangoPostingEngine())` and a side-by-side fixed `CommodityMovement` that issues metal out of the owned/vault commodity account. Tests cover ledger/account effects, outgoing commodity movement, idempotency, changed-payload rejection until correction/reversal, non-INR rejection, and rollback on commodity validation failure. The next recommended DEA slice is unfixed sale backend MVP: commodity issue plus open sale exposure without false final monetary receivable/revenue before rate fixing.
- DEA Phase 4 unfixed sale backend MVP slice is complete: `dea.services.unfixed_sale.post_unfixed_sale()` creates a posted commodity-intent voucher, outgoing `CommodityMovement`, and open sale `ExposureLine` without creating financial journal, ledger, account, or voucher-line rows before rate fixing. The service validates period openness, is idempotent by source plus economic payload, rejects changed payloads for the same source until correction/reversal exists, and rolls back completely on commodity/exposure validation failure.
- DEA Phase 4 sale-side rate fixing backend MVP is complete: `dea.services.rate_fixing.post_sale_rate_fixing()` fixes open sale exposure quantity, posts customer receivable/revenue financial effects, and closes or partially fixes the exposure atomically.
- DEA Phase 4 receipt/payment backend settlement MVP is complete: `dea.services.monetary_settlement` posts customer receipts and supplier payments through `PaymentVoucher`, stored voucher lines, and `PostVoucherCommand(DjangoPostingEngine())`. Customer receipts debit cash/bank and credit customer receivable; supplier payments debit supplier payable and credit cash/bank. Tests prove source/reference idempotency, changed-payload rejection, period locking, and that normal monetary settlement creates no commodity movements, exposures, or rate fixings.
- DEA Phase 4 karigar issue/receipt backend MVP is complete: `dea.services.karigar` posts karigar custody movements through posted commodity-intent vouchers and immutable `CommodityMovement` rows only. Issue moves metal from owned/vault to karigar custody; receipt moves metal from karigar custody back to owned/vault. Tests prove custody account party validation, idempotency, changed-payload rejection, period locking, and that karigar custody movement creates no financial journal/account rows, exposure lines, or rate fixings.
- DEA Phase 4/5 metal balance report backend MVP is complete: `dea.services.metal_balance_report.build_metal_balance_report()` returns selector-backed account rows, commodity totals, and fixed-status totals from `CommodityMovement` positions by commodity account, party, location, fixed status, and as-of date. It uses decimal quantity fields only, excludes synthetic adjustment/loss-gain offset accounts from default totals, and creates no financial rows.
- DEA Phase 4 financial trial balance hardening with commodity records present is complete for the current backend boundary: `ReportsService.trial_balance()` has regression coverage proving commodity movements, open exposures, standalone rate-fixing rows, and metal balance report reads do not affect financial trial balance totals or financial ledger rows.
- DEA Phase 5 exposure report backend MVP is complete: `dea.services.exposure_report.build_exposure_report()` returns active exposure rows and totals by commodity/side/status from `ExposureLine`, with party, commodity, side, status, and as-of filters plus optional reporting-only valuation. It creates no financial rows and does not introduce valuation snapshots or settlement allocation complexity.
- DEA Phase 5 party account and ledger statement boundary hardening is complete: focused tests prove period close, ledger audit, and account audit create monetary `LedgerStatement`/`AccountStatement` rows while commodity movements/exposures stay in metal and exposure reports. A narrow `Balance.get()` compatibility helper and explicit `Balance.__str__()` locale were added so existing audit paths work.
- DEA Phase 5 valuation report hardening is complete: `dea.services.valuation_report.build_valuation_report()` combines metal positions and exposure rows into a read-only valuation report with explicit valuation status totals. Focused tests cover valued rows, missing rates, unsupported currency/purity statuses, and no financial journal, voucher-line, rate-fixing, rate, movement, or exposure side effects.
- DEA Phase 6 first read-only report UI slice is complete: metal balance, exposure, and valuation reports now have login/workspace-gated DEA routes, templates, report-hub links, and route-level tests.
- DEA Phase 6 commodity report navigation polish is complete: the workspace sidebar and both DEA dashboard variants now expose read-only commodity report links without adding posting/editing workflows. The next recommended DEA slice is business-event UI design scaffolding only, before mutation screens are wired.
- DEA Phase 6 business-event UI scaffold is complete: `/dea/business-events/` is a GET-only dashboard for fixed/unfixed purchase, rate fixing, fixed/unfixed sale, receipt/payment, karigar issue/receipt, and commodity/financial report entry points. It links only to existing read-only reports, marks mutation workflows as not wired, and route tests prove it creates no accounting or commodity side effects. The next recommended DEA slice is a business-event form/preview contract before any POST screens are enabled.
- DEA Phase 6 business-event form/preview contract is complete in `docs/implementation/dea-business-event-form-preview-contract.md`: future event screens must collect business facts, render read-only accounting/commodity/exposure/inventory impact previews, and hand off to backend services only through explicit confirm POST paths. The next recommended DEA slice is a fixed-purchase preview-only screen with confirm posting disabled.
- DEA Phase 6 fixed-purchase preview-only screen is complete: `/dea/business-events/fixed-purchase/` now renders a business-facts form, POST-preview builds accounting/commodity/exposure/inventory impact through a side-effect-free preview service, and confirm posting remains disabled. Focused route tests prove the screen creates no voucher, voucher line, journal, ledger transaction, account transaction, payment voucher, commodity movement, exposure, or rate-fixing rows. The next recommended DEA slice is fixed-purchase source-draft persistence before any confirm posting is enabled.
- DEA Phase 6 fixed-purchase source-draft boundary is complete: `BusinessEventDraft` was added with tenant migration `dea.0036` to persist event type, source reference, event date, normalized payload, preview payload, and payload hash. Fixed-purchase preview POST now creates/updates only the draft/source row while confirm posting stays disabled and tests prove no accounting or commodity side effects.
- DEA Phase 6 fixed-purchase posting-readiness gate is complete: `/dea/business-events/fixed-purchase/` now renders a read-only readiness checklist over the saved draft, payload hash, open period, authenticated actor, account/ledger/commodity-account mappings, and existing-posted-voucher guard. Confirm posting remains disabled and tests prove the gate does not create accounting or commodity side effects. The next recommended DEA slice is a confirm-posting handoff contract for previewed fixed-purchase drafts before enabling the confirm button.
- DEA Phase 6 fixed-purchase confirm handoff service is complete: `dea.services.business_event_posting.confirm_fixed_purchase_draft()` row-locks the previewed draft, rejects stale payload/readiness failures, maps normalized draft payload into `FixedPurchasePostingPayload`, and delegates to `post_fixed_purchase()` so duplicate confirms return the existing voucher/journal/movement. The UI confirm button remains disabled. The next recommended DEA slice is a permissioned confirm endpoint plus posting-result/detail surface for fixed-purchase drafts.
- DEA Phase 6 fixed-purchase confirm endpoint/result surface is complete: `/dea/business-events/fixed-purchase/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, posts through `confirm_fixed_purchase_draft()`, keeps member-role users denied, treats duplicate submits idempotently, and redirects to a read-only fixed-purchase result page with voucher, journal entry, ledger/account, and commodity movement details. The next recommended DEA slice is fixed-purchase stale/error UX hardening plus draft list/navigation before copying the workflow to unfixed purchase.
- DEA Phase 6 fixed-purchase stale/error UX and navigation hardening is complete: the business-events dashboard now lists recent fixed-purchase drafts/results with posted/not-posted state, blocked fixed-purchase detail pages expose a re-preview recovery action, and route tests prove the dashboard/detail discovery remains read-only. The next recommended DEA slice is an unfixed-purchase preview-only screen using the same preview/draft/readiness contract while avoiding final monetary payable before rate fixing.
- DEA Phase 6 unfixed-purchase preview-only screen is complete: `/dea/business-events/unfixed-purchase/` collects supplier party, metal quantity/purity, commodity accounts, rate basis, and optional reporting valuation; persists an `UNFIXED_PURCHASE` preview draft; and renders read-only commodity receipt plus open purchase exposure impact while explicitly avoiding final monetary payable before rate fixing. Confirm posting remains disabled, and focused route tests prove no voucher, journal, ledger, account, movement, exposure, rate-fixing, or payment side effects. The next recommended DEA slice is an unfixed-purchase readiness/detail/navigation gate before enabling any confirm posting.
- DEA Phase 6 unfixed-purchase readiness/detail/navigation gate is complete: unfixed previews now render a read-only readiness checklist, `/dea/business-events/unfixed-purchase/<draft_id>/` shows draft facts, not-posted status, readiness, accounting note, commodity impact, and exposure impact, and the business-events dashboard lists recent unfixed-purchase drafts. Confirm posting remains disabled, and route tests prove the new discovery/detail surfaces remain read-only. The next recommended DEA slice is an unfixed-purchase confirm handoff service that maps a locked preview draft to `UnfixedPurchasePostingPayload` without enabling the UI confirm endpoint yet.
- DEA Phase 6 unfixed-purchase confirm endpoint/result surface is complete: `/dea/business-events/unfixed-purchase/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_unfixed_purchase_draft()`, handles duplicate submits idempotently, rejects member-role users, and redirects to a read-only result page showing the posted commodity-intent voucher, commodity movement, and open exposure rows. Tests prove this path creates no `JournalEntry`, `VoucherLine`, `LedgerTransaction`, `AccountTransaction`, `PaymentVoucher`, or `RateFixing` rows.
- DEA Phase 6 purchase rate-fixing preview/readiness screen is complete: `/dea/business-events/purchase-rate-fixing/` selects open purchase exposures, captures fixing date/weight/rate and supplier account plus inventory/payable ledgers, renders side-effect-free accounting and exposure impact, and keeps confirm posting disabled. Tests prove preview creates no new voucher, voucher-line, journal, ledger/account transaction, commodity movement, exposure, rate-fixing, or payment rows.
- DEA Phase 6 purchase rate-fixing source-draft boundary is complete: `BusinessEventDraft.EventType.PURCHASE_RATE_FIXING` was added with tenant migration `dea.0038`, and purchase rate-fixing preview POST now persists only the source/draft payload and renders a draft-based readiness checklist.
- DEA Phase 6 purchase rate-fixing confirm endpoint/result surface is complete: `/dea/business-events/purchase-rate-fixing/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_purchase_rate_fixing_draft()`, handles duplicate submits idempotently, rejects member-role users, and redirects to a read-only result page showing rate-fixing, voucher, journal, ledger/account, and exposure-allocation details without creating any physical commodity movement.
- DEA Phase 6 sale rate-fixing confirm endpoint/result surface is complete: `/dea/business-events/sale-rate-fixing/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_sale_rate_fixing_draft()`, handles duplicate submits idempotently, rejects member-role users, and redirects to a read-only result page showing sale rate-fixing, voucher, journal, ledger/account, and exposure-allocation details without creating any physical commodity movement.
- DEA Phase 6 receipt/payment preview-only screen is complete: `/dea/business-events/settlement/` captures customer receipt or supplier payment facts, persists only `CUSTOMER_RECEIPT` / `SUPPLIER_PAYMENT` `BusinessEventDraft` rows, and renders read-only cash/bank, party-account, payment, and commodity/no-commodity impact. Confirm posting remains disabled, and focused tests prove preview creates no voucher, payment voucher, voucher-line, journal, ledger/account transaction, commodity movement, exposure, or rate-fixing rows.
- DEA Phase 6 receipt/payment detail/readiness/navigation gate is complete: `/dea/business-events/settlement/<draft_id>/` shows saved settlement draft facts, posting readiness, accounting impact, payment impact, and explicit no-commodity impact while keeping confirm posting disabled. The business-events dashboard links recent receipt/payment drafts to this detail page.
- DEA Phase 6 receipt/payment confirm handoff service is complete: `confirm_monetary_settlement_draft()` row-locks a previewed `CUSTOMER_RECEIPT` / `SUPPLIER_PAYMENT` draft, rejects stale payload/readiness blockers, maps normalized payload into `CustomerReceiptPayload` or `SupplierPaymentPayload`, and delegates to `post_customer_receipt()` / `post_supplier_payment()` idempotently.
- DEA Phase 6 receipt/payment confirm endpoint/result surface is complete: `/dea/business-events/settlement/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_monetary_settlement_draft()`, handles duplicate submits idempotently, rejects member-role users, and redirects to a read-only settlement result page showing payment voucher, voucher, journal, ledger/account rows, payment impact, and explicit no-commodity impact. Tests prove this path creates no `CommodityMovement`, `ExposureLine`, or `RateFixing` rows.
- DEA Phase 6 karigar issue/receipt preview screens are complete: `/dea/business-events/karigar/` captures issue or receipt custody facts, persists `KARIGAR_ISSUE` / `KARIGAR_RECEIPT` `BusinessEventDraft` rows through tenant migration `dea.0043`, renders readiness, and shows commodity-only custody movement impact with no financial, exposure, rate-fixing, or payment effects. Confirm posting remains disabled. The next recommended DEA slice is a karigar confirm handoff service without enabling the UI confirm endpoint.
- DEA Phase 6 karigar confirm handoff service is complete: `confirm_karigar_movement_draft()` row-locks previewed `KARIGAR_ISSUE` / `KARIGAR_RECEIPT` drafts, rejects stale payload/readiness blockers, maps drafts to `KarigarIssuePayload` / `KarigarReceiptPayload`, and delegates to `post_karigar_issue()` / `post_karigar_receipt()` idempotently. Tests prove it creates one commodity-intent voucher and one custody `CommodityMovement` with no financial, exposure, rate-fixing, or payment rows. The next recommended DEA slice is the permissioned karigar confirm endpoint/result surface.
- DEA Phase 6 karigar confirm endpoint/result surface is complete: `/dea/business-events/karigar/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_karigar_movement_draft()`, handles duplicate submits idempotently, rejects member-role users, and redirects to the karigar detail page showing the posted commodity-intent voucher and custody movement. Tests prove this path creates no financial, exposure, rate-fixing, or payment rows. The next recommended DEA slice is a Phase 6 completion checkpoint before Phase 7 legacy cleanup.
- DEA Phase 6 completion checkpoint is complete in `docs/implementation/dea-phase-6-business-event-checkpoint.md`: the event-impact matrix now records which business events create financial rows, commodity movements, exposure rows, rate fixings, and payment vouchers. Focused backend, UI, report, trial-balance, statement-boundary, and migration dry-run checks passed individually. The next recommended DEA slice is Phase 7 cleanup readiness audit before hiding or deleting legacy DEA surfaces.
- DEA Phase 7 cleanup readiness audit has started in `docs/implementation/dea-phase-7-cleanup-readiness-audit.md`: legacy/accountant DEA surfaces and direct posting paths are classified before any deletion, and guard tests now prove key accountant routes resolve plus runtime DEA/Girvi modules do not import `posting/legacy_direct_write_engine.py`. The next recommended slice is focused characterization of `views/expense.py::post_expense_voucher()`.
- DEA Phase 7 expense-post characterization is complete: `views/expense.py::post_expense_voucher()` now has tests proving direct-payment idempotency, duplicate journal prevention, and closed-period no-materialization. The next recommended slice is proving old helper functions in `views/voucher.py` are runtime-dead, then deleting them in a narrow patch if voucher post/reverse characterization still passes.
- DEA Phase 7 dead voucher-helper cleanup is complete: old direct materialization helper definitions were removed from `views/voucher.py` after focused post/reverse tests passed, and a guard test now prevents those helpers from returning. The next recommended slice is a permission audit for legacy/accountant DEA surfaces before navigation hiding or relabeling.
- DEA Phase 7 accountant permission hardening is complete for the first high-risk legacy surfaces: voucher hub, generic voucher CRUD/post/reverse, payment voucher CRUD, expense voucher CRUD/post, manual journal voucher CRUD, and opening-balance endpoints now use shared owner/admin/accountant DEA access helpers. The next recommended slice is navigation cleanup so normal staff are guided to business events and reports while accountant/admin users retain legacy/manual accounting tools.
- DEA Phase 7 sidebar navigation cleanup is complete for current workspace navigation: DEA sidebar now points normal users to business events plus financial/commodity reports, while legacy/manual links (voucher, payment, expense, manual journal, opening balance, period controls, diagnostics) are grouped under an accountant tools block for `Owner`/`Admin`/`Accountant` roles.
- DEA Phase 7 dashboard/header navigation alignment is complete for current dashboard surfaces: standard and enhanced DEA dashboards now default to business-events/report quick actions and workflows for normal staff, while accountant-only manual links stay visible for `Owner`/`Admin`/`Accountant` users only. Focused scaffold tests now assert owner-vs-member visibility boundaries.
- DEA Phase 7 legacy-surface gating refinement is complete for current dashboard panels: member users now see reduced recent-vouchers/recent-entries panels with direct navigation disabled, while owner/admin/accountant users retain full drilldown links and COA preview visibility. Both dashboard templates conditionally hide legacy-only panels for non-accountant roles, and role-visibility tests have been extended to verify member-to-accountant boundaries across both dashboard variants. Passed 76 role-gating tests.
- DEA Phase 7 accounting tools documentation is complete: comprehensive inventory of all 100+ legacy DEA accounting tool surfaces now documented with role-gating analysis and Phase 8+ recommendations. Identifies inconsistencies (Period CRUD currently LoginRequired instead of AccountantRequired; Bank Reconciliation audit needed) and deprecation candidates (legacy Journal Entry views if JournalEntryVoucher fully adopted). Document at [docs/implementation/dea-phase7-accounting-tools-inventory.md](implementation/dea-phase7-accounting-tools-inventory.md).
- DEA Phase 7.1 business event posting is complete: all 8 event types (fixed/unfixed purchase, purchase rate fixing, fixed/unfixed sale, sale rate fixing, monetary settlement, karigar movement) now have confirm buttons enabled via `confirm_disabled = False` in [apps/tenant_apps/dea/views/business_events.py](apps/tenant_apps/dea/views/business_events.py). All 73 scaffold tests pass. Users can now create, preview, and confirm business events to post commodity movements and accounting entries. Backend services handle idempotency, role gating, and duplicate-submit protection.
- DEA Phase 7.2 commodity CRUD is complete: accountant-only Commodity Master screens are now available at `/dea/commodities/` for list/search/filter, create, detail, edit, and guarded deactivate workflows. Navigation now exposes Commodity Master under accountant tools and in reports hub for accountant roles. Focused coverage exists in `apps/tenant_apps/dea/tests/test_commodity_master_views.py` for permission boundaries, create/update/deactivate behavior, and active-only business-event commodity queryset behavior.
- DEA Phase 7.3 commodity account quick setup is complete for the MVP-safe slice: Commodity detail now exposes a quick setup action that idempotently creates standard `OWNED_STOCK` and `VAULT` commodity accounts, while explicitly leaving `KARIGAR_CUSTODY` manual because that model requires a Party. Sidebar discoverability for Commodity Master is now explicit in the DEA app section, and focused tests cover owner visibility plus quick setup idempotency.
- DEA Phase 7.3 follow-up manual karigar custody UX is complete: Commodity detail now also exposes a selected-Party form that creates or reuses a `KARIGAR_CUSTODY` commodity account for that commodity-party pair, with optional custom code/name/location overrides and active-party-only selection. This closes the immediate UX gap for karigar issue/receipt workflows without adding a broader account wizard.
- DEA Phase 7.3 karigar posting UX is now aligned with the live confirm endpoint: the karigar preview screen shows the real confirm CTA when readiness passes, instead of the obsolete Phase 6 preview-only disabled-posting message. Operator guidance is documented in the Phase 7 roadmap: issue flows move metal from `OWNED_STOCK` or `VAULT` to the selected Party's `KARIGAR_CUSTODY`, while receipt flows reverse that direction back into `OWNED_STOCK` or `VAULT`.
- DEA Phase 7 business-event wording cleanup now improves purchase UX: fixed/unfixed purchase preview forms label commodity account inputs as supplier-side source and workspace destination stock/vault accounts (instead of raw from/to terminology), reducing operator confusion without changing posting behavior.
- Subscription Phase 1 implementation is now in place: a shared `SubscriptionAccessService` centralizes workspace access, subscription activity, and feature entitlement evaluation; middleware and the org subscription decorator now delegate to it; and regression tests cover active, inactive, and feature-blocked access decisions.
- Subscription Phase 3 seat-limit enforcement is now in place: workspace `max_users` capacity resolves through subscription entitlements/plan defaults, invitation and membership creation flows enforce capacity limits, and invitation signal/signup fallback paths now route through control-plane membership creation so seat limits cannot be bypassed via alternate acceptance paths.
- Subscription seat-capacity hardening follow-up is complete: orgs now exposes a dedicated `membership_capacity` service wrapper over subscription capacity helpers, team invitation/membership templates now show seat usage plus upgrade guidance, invitation accept now fails gracefully on seat-limit validation, and role-change flow is capacity-aware for future non-seat to seat role transitions.
- Subscription Phase 3 workspace invitation UX closeout is complete: sent workspace invitations now render the same seat-capacity summary and upgrade guidance as team invite/member screens, with capacity context sourced from the org membership-capacity wrapper.
- Subscription Phase 4 entitlement-gated module visibility has started: workspace module cards now include an initial entitlement-evaluated slice (`advanced_reporting`, `api`, `custom_fields`) driven by `SubscriptionAccessService` access decisions, including active/locked/billing-required states and upgrade guidance.
- Subscription Phase 4 module map is now registry-driven for all cards: workspace modules use a single definition list with default state plus optional `feature_code`, and entitlement evaluation is consistently applied through `SubscriptionAccessService` for gated cards while non-gated cards preserve explicit active/planned states.
- Subscription Phase 4 follow-up is documented as non-blocking for Phase 5: expanding feature-code coverage beyond the initial module set is deferred while the route-level enforcement pattern is rolled out.
- Subscription Phase 5 has started with route-level entitlement enforcement: `advanced_reporting` is now enforced at the DEA reports-hub entry route via a reusable `subscription_feature_required()` decorator, with redirect-to-billing behavior covered by tenant DEA tests.
- Subscription UI discoverability is now improved in the authenticated top navbar: workspace owners now have direct links to the billing dashboard and subscription plans alongside the existing workspace-management shortcuts.
- DEA Phase 7 period CRUD and bank reconciliation permission hardening is complete: all accounting period views (list, detail, create, update, adjustments, close, lock, unlock, transactions, balances, report, status, delete) now require owner/admin/accountant access via `@dea_accountant_required`; all bank reconciliation views (list, detail, import, auto-match, manual-match, unmatch) are now gated by `DeaAccountantRequiredMixin` / `@dea_accountant_required`. Three new permission boundary tests prove member users are denied period and reconciliation surfaces. All 6 permission boundary tests pass.
- DEA Phase 8 JEV surface relabeling is complete: Journal Entry Voucher UI now uses "Manual Journal Entry (Advanced)" in page titles, breadcrumbs, sidebar nav, and the voucher hub footer. The list page includes a dismissible advisory banner directing normal users to Business Events for day-to-day workflows. No route or model changes; purely UI discoverability improvement.
- SaaS IA Phase 2 first slice is complete for route/template naming only: active public/auth/global/tenant templates now extend intent-specific base aliases, and `django_project.shared_urlpatterns` exposes named route groups without changing the effective URL map.
- SaaS IA Phase 2.2 route intent cleanup is complete for URLConf grouping and regression coverage. `django_project/test_route_intent.py` now guards active public/tenant URLConf settings, shared route aggregate order, public URLConf tenant-prefix exclusion, tenant ERP prefix grouping, and legacy public URLConf parity.
- SaaS IA Phase 2.3 template layout cleanup is complete for clear first-party stragglers. Onboarding, subscription, DEA reconciliation/report base, dynamic preference, simple upload, company legacy, and error templates now target intent aliases, and `django_project/test_template_layout_intent.py` guards direct low-level layout usage plus alias block contracts.
- SaaS IA Phase 2.4 workspace settings layout separation is complete for the current settings shell. Workspace detail/preferences/team/invitation/leave/delete pages now target `base_workspace_settings.html`, the management layout exposes future settings-sidebar include points, and layout-intent tests guard both decisions.
- SaaS IA Phase 2.5 shell render smoke tests are complete. `django_project/test_shell_render_smoke.py` renders all five active shell aliases and checks that the expected content block markers survive through the real base layouts.
- SaaS IA Phase 2.6 route/template inventory documentation is complete in [docs/ui/route_template_inventory.md](ui/route_template_inventory.md). The next recommended SaaS IA slice is Phase 3 navigation and workspace switcher planning, still keeping compatibility routes in place.
- SaaS IA Phase 3.1 navigation and workspace switcher planning is complete in [docs/ui/navigation_workspace_switcher_plan.md](ui/navigation_workspace_switcher_plan.md). `django_project/test_navigation_intent.py` now protects the current workspace switcher partial contract, tenant sidebar source-of-truth decision, and separate management/tenant navigation surfaces. The next recommended slice is Phase 3.2: replace the inline topbar workspace dropdown with the reusable switcher partial and add authenticated shell render coverage.
- SaaS IA Phase 3.2 workspace switcher reuse is complete. `templates/components/navigation/main_nav.html` now delegates workspace switching to `templates/components/navigation/workspace_switcher.html` using a navbar variant, while the existing standalone switcher remains available. `django_project/test_shell_render_smoke.py` now covers authenticated global and tenant shell switcher rendering. The next recommended slice is Phase 3.3: begin extracting the duplicated workspace settings sidebar links into `components/navigation/workspace_settings_sidebar.html` for desktop first, then mobile.
- SaaS IA Phase 3.3 desktop settings-sidebar extraction is complete. `templates/layouts/management.html` now delegates desktop workspace settings/team/invitation links to `templates/components/navigation/workspace_settings_sidebar.html` with a desktop variant, and `django_project/test_template_layout_intent.py` guards that ownership. The next recommended slice is Phase 3.4: route the mobile management offcanvas through the same settings sidebar partial using a mobile variant, then remove duplicated mobile workspace settings links.
- SaaS IA Phase 3.4 mobile settings-sidebar extraction is complete. `templates/layouts/management.html` now delegates mobile workspace settings/team/invitation links to `templates/components/navigation/workspace_settings_sidebar.html` with a mobile variant, and `django_project/test_template_layout_intent.py` guards both desktop and mobile ownership. The next recommended slice is Phase 3.5: extract the remaining duplicated account-management links from desktop/mobile management navigation into a focused account sidebar partial without changing labels or routes.
- SaaS IA Phase 3.5 account-management sidebar extraction is complete. `templates/layouts/management.html` now delegates desktop and mobile account links to `templates/components/navigation/account_sidebar.html`, preserving invitations, owner billing, account settings, and profile routes. `django_project/test_template_layout_intent.py` guards that ownership. The next recommended slice is Phase 3.6: extract the remaining duplicated workspace-manager links (`My Workspaces`, `New Workspace`) into a focused workspace manager sidebar partial for desktop and mobile variants.
- SaaS IA Phase 3.6 workspace-manager sidebar extraction is complete. `templates/layouts/management.html` now delegates desktop and mobile workspace-manager links to `templates/components/navigation/workspace_manager_sidebar.html`, preserving `workspace_selector` and `workspace_create`. `django_project/test_template_layout_intent.py` guards the ownership. The next recommended slice is Phase 3.7: review the management shell naming/comments and remove obsolete "duplicate sidebar content" wording without changing behavior.
- SaaS IA Phase 3.7 management shell cleanup is complete. `templates/layouts/management.html` now uses clean ASCII comments, stale duplicate-sidebar wording is removed, and `docs/ui/navigation_workspace_switcher_plan.md` records the final management navigation partial inventory. The next recommended slice is Phase 3.8: run a compatibility review of management-shell rendered output and route names before visual polish.
- SaaS IA Phase 3.8 management-shell compatibility review is complete. `django_project/test_shell_render_smoke.py` now renders an authenticated owner management shell and asserts key workspace-manager, workspace-settings, and account-management route targets and labels survive the partialization. The next recommended slice is Phase 3.9: prepare a visual-polish checklist for the global/settings management shell before changing CSS or layout density.
- SaaS IA Phase 3.9 management shell visual-polish checklist is complete in [docs/ui/management_shell_visual_polish_checklist.md](ui/management_shell_visual_polish_checklist.md). The next recommended slice is Phase 3.10: implement the first restrained management-shell visual polish pass while preserving route names, labels, partial ownership, and permission behavior.
- SaaS IA Phase 3.10 first management-shell visual polish pass is complete. `templates/layouts/management.html` and the management sidebar partials now use neutral control-plane styling, shared management nav-link classes, and mobile active-state parity. The next recommended slice is Phase 3.11: browser/screenshot review across desktop and mobile widths, followed by only targeted overflow or spacing corrections.
- SaaS IA Phase 3.11 rendered management-shell review is complete. A temporary rendered shell fixture was generated and local Chrome headless screenshot attempts were made, but this environment did not produce screenshot files. The rendered HTML review found and fixed the default base-container constraint through a backward-compatible `main_wrapper_class` block. The next recommended slice is Phase 3.12: add a reproducible browser/live-server visual smoke path before additional visual polish.
- SaaS IA Phase 3.12 reproducible management-shell visual smoke coverage is complete. `django_project/test_management_shell_visual_smoke.py` renders an authenticated owner management shell and guards the app wrapper, desktop/mobile management nav classes, active states, and control-plane route safety. The next recommended slice is Phase 3.13: extract management-shell inline CSS into a dedicated static stylesheet without visual behavior changes.
- SaaS IA Phase 3.13 management-shell CSS extraction is complete. The shell styles now live in `static/css/management.css`, `layouts/management.html` loads that file through Django staticfiles, and tests guard both extraction and rendered shell behavior. The next recommended slice is Phase 3.14: static asset readiness checks for the new stylesheet, including `findstatic` and a safe collectstatic check path.
- SaaS IA Phase 3.14 static asset readiness is complete. `findstatic css/management.css --verbosity 2` resolves the new stylesheet from `static/css/management.css`, `collectstatic --dry-run --noinput --verbosity 1` succeeds and includes the file, and visual smoke tests now guard staticfiles discovery. The next recommended slice is Phase 3.15: final Phase 3 navigation/management-shell review and phase-level commit preparation.
- SaaS IA Phase 3.15 final navigation/management-shell review is complete in [docs/ui/phase3_navigation_management_shell_review.md](ui/phase3_navigation_management_shell_review.md). The next recommended action is to commit the Phase 3 set, then start Phase 4 invitation/team flow cleanup.
- SaaS IA Phase 4.1 invitation/team flow intent audit is complete for documentation and regression guards. Current incoming invitation routes remain global/account surfaces, sent invitation and team-member routes remain workspace settings surfaces, and no URL or behavior changes were made. The next recommended slice is Phase 4.2 route-intent cleanup without URL breakage: clarify route grouping/naming intent in code/tests before any canonical aliases.
- SaaS IA Phase 4.2 route-intent cleanup is complete without URL breakage. The next recommended slice is Phase 4.3 copy and heading clarification: distinguish received invitations from sent workspace invitations, clean up existing mojibake, and keep route names plus form actions unchanged.
- SaaS IA Phase 4.3 copy and heading clarification is complete. The next recommended slice is Phase 4.4 workspace-scoped redirect cleanup: keep old URLs working, but make invite success and revoke/list returns land in the relevant workspace settings context.
- SaaS IA Phase 4.4 workspace-scoped redirect cleanup is complete. The next recommended slice is Phase 4.5 accept/decline characterization: prove how direct django-invitations accept links differ from the custom orgs accept/decline flow before replacing or delegating that entrypoint.
- SaaS IA Phase 4.5 accept/decline characterization is complete. The next recommended slice is Phase 4.6 authorization coverage for invite, revoke, role change, remove member, self-leave, and selected-workspace fallback before replacing the direct accept entrypoint.
- SaaS IA Phase 4.6 authorization coverage is complete. The next recommended slice is Phase 4.7 scope decision: add canonical compatibility aliases or wrap the direct invitation accept route with an orgs-owned adapter using the now-characterized policy boundaries.
- SaaS IA Phase 4.7 direct invitation accept adapter is complete. The next recommended step is Phase 4 final review and phase-level commit preparation before starting canonical route aliases or Phase 5 authorization cleanup.
- SaaS IA Phase 4 final review is complete. The next recommended action is to commit the Phase 4 set, then begin canonical route aliases or Phase 5 authorization cleanup as a separate phase.
- SaaS IA canonical route aliases are phase-reviewed in [docs/ui/canonical_route_aliases_phase_review.md](ui/canonical_route_aliases_phase_review.md). Management navigation now uses `app_workspaces`, `app_workspace_create`, `app_invitations`, `workspace_settings_home`, `workspace_settings_preferences`, `workspace_settings_team`, `workspace_settings_invite`, and `workspace_settings_invitations` while legacy route names and URLs remain active-compatible. Invite POST success, invite-success back links, and revoke returns now use `workspace_settings_invitations`; the legacy `team_invite_success` route remains available.
- SaaS IA Phase 5.1 authorization inventory and guard tests are complete for the first baseline slice.
- SaaS IA Phase 5.2 middleware canonical settings path extraction is complete.
- SaaS IA Phase 5.3 middleware tenant-prefix coverage is complete.
- SaaS IA Phase 5.4 Party access helper scaffolding is complete.
- SaaS IA Phase 5.5 Party read/export authorization is complete. The next recommended slice is to convert Party mutation paths to the new helpers in small groups, starting with create/update/customer-convert before nested contact/address/document mutations.
- SaaS IA Phase 5.6 Party simple mutation authorization is complete. The next recommended slice is to convert nested Party mutation paths to the new helpers in small groups, starting with profile photo and contact/address mutations.
- SaaS IA Phase 5.7 Party profile mutation authorization is complete. The next recommended slice is to convert the remaining nested Party mutation paths in small groups, starting with identifiers, documents, and relationships before roles and merge.
- SaaS IA Phase 5.8 Party KYC/relationship mutation authorization is complete. The next recommended slice is to convert the final Party nested mutation paths: role add/end and duplicate merge.
- SaaS IA Phase 5.9 final Party mutation authorization is complete. The next recommended action is a Phase 5 Party authorization review and phase-level commit checkpoint before starting Product authorization cleanup.
- SaaS IA Phase 5 Party authorization review is complete. The next recommended action is starting Product authorization cleanup as the next separate slice; skip broad Contact cleanup in favor of the Party cutover.
- SaaS IA Phase 5.10 Product catalog authorization is complete. The next recommended action is Product stock authorization review, then Product pricing/image/attribute route groups.
- SaaS IA Phase 5.11 Product stock authorization is complete. The next recommended action is Product pricing authorization cleanup, then Product image/attribute route groups.
- SaaS IA Phase 5.12 Product pricing/image/attribute authorization is complete.
- SaaS IA Phase 5.13 Rates/Notify authorization is complete.
- SaaS IA Phase 5.14 authorization closeout is complete for the current SaaS IA scope. The next recommended action is a Phase 5 review/commit checkpoint before starting Phase 6 onboarding.
- SaaS IA Phase 6.1 onboarding inventory and guard tests are complete.
- SaaS IA Phase 6.2 read-only workspace setup checklist service is complete.
- SaaS IA Phase 6.3 workspace dashboard checklist surface is complete.
- SaaS IA Phase 6.4 workspace settings setup page is complete.
- SaaS IA Phase 6.5 onboarding completion routing is complete.
- SaaS IA Phase 6.6 onboarding workspace creation extraction is complete.
- SaaS IA Phase 6.7 onboarding team invitation extraction is complete.
- SaaS IA Phase 6.8 workspace setup completion/dismiss state is complete.
- SaaS IA Phase 6.9 onboarding review is complete. The next recommended action is to commit Phase 6 as a single phase-level commit, then start Phase 7 modern fintech UI polish.
- SaaS IA Phase 7.1 modern fintech UI polish plan and guard tests are complete. The next recommended action is Phase 7.2: add small management/setup visual vocabulary to `static/css/management.css` and apply it to the workspace setup page only.
- SaaS IA Phase 7.2 workspace setup visual vocabulary is complete. The next recommended action is Phase 7.3: polish the workspace dashboard setup card using the new vocabulary where practical, without changing setup-state behavior.
- SaaS IA Phase 7.3 dashboard setup-card polish is complete. The next recommended action is Phase 7.4: extract repeated setup checklist markup into a shared partial only if behavior remains exactly unchanged.
- SaaS IA route-map note: Phase 2 is complete for route/template intent standardization, but the full target `/w/<workspace_slug>/...` route map from the IA audit has not been implemented yet. That should remain a separate future alias/redirect phase after the current `/app/...` and `/workspace/<id>/settings/...` aliases stabilize.
- SaaS IA Phase 7.4 setup checklist task partial extraction is complete. The next recommended action is Phase 7.5: review and polish the global workspace selector/workspace-list surface without changing route behavior or membership checks.
- SaaS IA Phase 7.5 global workspace selector polish is complete. The next recommended action is Phase 7.6: public/auth page polish planning and guard tests before visual changes.
- SaaS IA Phase 7.6 public/auth route-template inventory and guard tests are complete. `docs/ui/phase7_public_auth_polish_plan.md` records current pages/allauth/invitation route ownership, template shell ownership, missing pricing/short-auth aliases, and missing public templates. The next recommended action is Phase 7.7: first public/auth visual polish pass while preserving current allauth/social-auth/invitation behavior.
- SaaS IA Phase 7.7 first public/auth visual polish pass is complete. `static/css/public.css` owns public/auth visual classes, public/auth shell aliases load it, the landing page has a product-specific SaaS ERP funnel without inline CSS or a remote placeholder image, and login/signup/password-reset pages share a consistent auth layout while preserving allauth/social-auth behavior. The next recommended action is Phase 7.8: render-review public/auth pages and apply only focused overflow/spacing fixes if needed.
- SaaS IA Phase 7.8 public/auth render review is complete. Render smoke coverage now hits `/`, `/accounts/login/`, `/accounts/signup/`, and `/accounts/password/reset/`; auth pages no longer crash when a Google client id exists without a configured django-allauth `SocialApp` because Google OAuth CTA rendering is gated by `GOOGLE_OAUTH_ENABLED`. The next recommended action is Phase 7.9: tenant ERP dashboard/navigation density polish without changing business workflows.
- SaaS IA Phase 7.9 tenant ERP dashboard/navigation density polish is complete. `static/css/workspace.css` now owns tenant shell/sidebar/dashboard visual classes, `base_tenant.html` loads it, tenant layout/sidebar inline style blocks are removed, and the workspace dashboard uses denser stat/quick-action classes without changing links, permission conditions, setup-card behavior, tenant isolation, or posting workflows.
- SaaS IA Phase 7.10 first-pass UI polish review is complete in [docs/ui/phase7_modern_fintech_ui_polish_review.md](ui/phase7_modern_fintech_ui_polish_review.md). The review records that Phase 7 was UI infrastructure and surface cleanup, not a final high-fidelity redesign, and keeps the target route-map rollout plus deeper visual redesign deferred. The next recommended action is to commit the Phase 7 set, then start Phase 8 regression consolidation.
- SaaS IA Phase 8.1 regression consolidation planning is complete in [docs/ui/phase8_regression_consolidation_plan.md](ui/phase8_regression_consolidation_plan.md). The plan maps existing guard files, regression buckets, deferred alias/design work, and the no-runtime-change acceptance criteria for Phase 8. The next recommended action is Phase 8.2: route boundary regression tests for current aliases, legacy URLs, and intentionally absent future aliases.
- SaaS IA Phase 8.2 route boundary regression is complete. `django_project/test_route_intent.py` now guards current `/app/...` and `/workspace/<id>/settings/...` aliases across public and tenant URLConFs, legacy allauth/invitation/orgs compatibility paths, representative tenant ERP paths, public URLConf tenant exclusion, and intentionally absent future aliases such as `/pricing/`, short auth aliases, `/invitations/accept/<key>`, and `/w/<workspace_slug>/...`. The next recommended action is Phase 8.3: template/shell regression tests for base-template ownership and static stylesheet contracts.
- SaaS IA Phase 8.3 template/shell regression is complete. `django_project/test_template_layout_intent.py` now guards shell alias ownership, public/auth `css/public.css`, tenant `css/workspace.css`, management/workspace extracted shell no-inline-style contracts, and the documented root `layouts/base.html` / `main_nav.html` inline style debt. The next recommended action is Phase 8.4: public/auth render and compatibility tests, including missing-template documentation.
- SaaS IA Phase 8.4 public/auth render and compatibility regression is complete. `django_project/test_phase7_public_auth_render_smoke.py` now guards renderable public pages, allauth login/signup/password-reset rendering, Google OAuth CTA gating, current allauth route names, current django-invitations `/invitations/accept-invite/<key>` compatibility, invalid invite fail-closed behavior, and documented missing public templates. The next recommended action is Phase 8.5: workspace switching, setup, and onboarding regression tests.
- SaaS IA Phase 8.5 workspace/setup/onboarding regression is complete. `django_project/test_onboarding_phase6_intent.py` now guards canonical and legacy workspace setup routes, canonical setup-state form targets, membership-safe workspace switching before selected-workspace mutation, safe `next` handling, `WORKSPACE_SWITCH` audit logging, and the presence of focused onboarding runtime regression files.
- SaaS IA Phase 8.6 invitation/team regression is complete. `django_project/test_invitation_team_flow_intent.py` now guards the presence of focused runtime tests for invite permissions, role-grant policy, revoke denial, team remove/change-role gates, sole-owner self-leave, sent-invitation workspace context, and direct accept adapter behavior; it also guards orgs view/control-plane ownership for accept/revoke/member mutation policy and audit actions.
- SaaS IA Phase 8.7 authorization regression is complete. `django_project/test_authorization_surface_intent.py` now guards exact tenant ERP prefix coverage, middleware workspace-required coverage, Party/Product/Rates/Notify/utility data-tool guards, Contact's documented legacy gap, the intentionally public Notify v2 webhook, and DEA/Girvi as separate domain-specific permission tracks.
- SaaS IA Phase 8.8 regression closeout is complete in `docs/ui/phase8_regression_consolidation_review.md`. The review records completed guard coverage, deferred scope, compatibility findings, verification commands, expected test log noise, and the tests/documentation-only commit boundary. The next recommended action is to commit the Phase 8 set, then start a follow-on alias/template phase for `/pricing/`, missing public templates, short auth aliases, `/invitations/accept/<key>`, and the full `/w/<workspace_slug>/...` route-map rollout.
- SaaS IA Phase 9.1 public/auth alias-template rollout planning is complete in `docs/ui/public_auth_alias_template_rollout_plan.md`, with guard coverage in `django_project/test_public_auth_alias_template_rollout_intent.py`. Runtime behavior is unchanged: `/pricing/`, short auth aliases, `/invitations/accept/<key>`, missing public templates, and `/w/<workspace_slug>/...` remain deferred. The next recommended action is Phase 9.2: add `/pricing/` and the missing public templates without changing auth aliases or invitation aliases yet.
- SaaS IA Phase 9.2 pricing and missing public templates are implemented. `/pricing/` now resolves through `PricingPageView`, and `templates/pages/pricing.html`, `tenant.html`, `cancellation_and_refund.html`, `contact.html`, `help.html`, and `faq.html` render through `base_public.html`. Short auth aliases, `/invitations/accept/<key>`, and `/w/<workspace_slug>/...` remain deferred. The next recommended action is Phase 9.3: add short auth aliases while preserving `/accounts/...` compatibility paths.
- SaaS IA Phase 9.3 short auth aliases are implemented. `/login/`, `/signup/`, and `/password/reset/` redirect to the existing allauth `/accounts/...` implementation paths while preserving query strings. `/invitations/accept/<key>` and `/w/<workspace_slug>/...` remain deferred. The next recommended action is Phase 9.4: add the public invitation accept alias to the orgs-owned adapter.
- SaaS IA Phase 9.4 public invitation accept alias is implemented. `/invitations/accept/<key>` now resolves as `public_invitation_accept` to the orgs-owned `team_accept_invitation` adapter while the django-invitations `/invitations/accept-invite/<key>` compatibility path remains available. The next recommended action is Phase 9.5: public/auth alias rollout review and commit preparation before the separate `/w/<workspace_slug>/...` route-map phase.
- SaaS IA Phase 9.5 public/auth alias-template rollout review is complete in `docs/ui/public_auth_alias_template_rollout_review.md`. The review records completed pricing/templates/auth/invitation aliases, compatibility findings, verification commands, and the commit boundary. The next recommended action is to commit this phase, then start separate `/w/<workspace_slug>/...` route-map planning before slug routes are added.
- SaaS IA Phase 10.1 workspace slug route-map planning is complete in `docs/ui/workspace_slug_route_map_plan.md`, with guard coverage in `django_project/test_workspace_slug_route_map_intent.py`. Runtime behavior is unchanged and `/w/<workspace_slug>/...` routes remain intentionally absent until slug source, middleware extraction, membership ordering, and redirect targets are decided. The next recommended action is Phase 10.2: decide whether the initial slug source is `Company.schema_name` or a dedicated `Company.slug`.
- SaaS IA Phase 10.2 slug source decision is complete. `/w/<workspace_slug>/...` will initially use `Company.schema_name` as a compatibility slug, avoiding a shared-schema migration while route behavior is proven. A dedicated immutable `Company.slug` remains deferred until workspace rename/branding requirements justify it. The next recommended action is Phase 10.3: add middleware slug extraction by `schema_name` while keeping runtime slug routes absent.
- SaaS IA Phase 10.3 middleware slug extraction is complete. `SecureWorkspaceMiddleware` can now extract `/w/<workspace_slug>/...` path candidates and resolve them by `Company.schema_name`, while ignoring the public schema slug. No `/w/...` URL patterns are live yet, so runtime route behavior remains unchanged. The next recommended action is Phase 10.4: add minimal slug aliases for dashboard and workspace settings.
- SaaS IA Phase 10.4 minimal workspace slug aliases are live. `CANONICAL_WORKSPACE_SLUG_URLPATTERNS` now exposes `/w/<workspace_slug>/`, `/w/<workspace_slug>/settings/`, `/settings/preferences/`, `/settings/team/`, and `/settings/invitations/` as redirect aliases to existing id-based dashboard/settings views. Tenant ERP section aliases remain absent. The next recommended action is Phase 10.5: add Party, loans, inventory, and accounting section aliases in small groups, skipping Contact.
- SaaS IA Phase 10.5 tenant ERP section aliases are live for current stable module entrypoints: `/w/<workspace_slug>/parties/` -> Party, `/loans/` -> Girvi, `/inventory/` -> Product, and `/accounting/` -> DEA. Contact is intentionally skipped because Party is the replacement. Operations, sales, purchase, commodity, and reports remain absent until product targets are selected. The next recommended action is Phase 10.6: move selected navigation links to slug aliases where workspace schema context is reliable.
- SaaS IA Phase 10.6 selected navigation cutover is complete. Tenant sidebar dashboard, Parties, Girvi, and Product links now target slug aliases, and workspace settings sidebar home/preferences/team/sent-invitations links use slug aliases when `ew.schema_name` is available. Setup, invite member, subscription, reports, business events, commodity, accounting tools, rates, notifications, and data tools stay on existing routes. The next recommended action is Phase 10.7: review, verify, and commit the workspace slug route-map phase.
- SaaS IA Phase 10.7 workspace slug route-map review is complete in `docs/ui/workspace_slug_route_map_review.md`. The review records completed slug aliases, compatibility findings, verification, deferred target routes, and the commit boundary. The next recommended action after commit is to choose targets for the remaining deferred `/w/<workspace_slug>/...` routes or start the customer/member portal IA phase.
- SaaS IA Phase 11.1 deferred workspace slug target selection is complete in `docs/ui/workspace_slug_deferred_targets_plan.md`. Operations/sales/purchase target the DEA business-events dashboard; commodity targets DEA commodity master; reports targets DEA reports hub; profile/billing/accounting target existing workspace update, subscription dashboard, and chart of accounts surfaces; roles and numbering have interim targets; modules and security remain absent until real workspace-owned screens exist. The next recommended action is Phase 11.2: implement only the safe redirect aliases.
- SaaS IA Phase 11.2 safe deferred workspace slug aliases are implemented. `/w/<workspace_slug>/operations/`, `/sales/`, and `/purchase/` redirect to DEA business events; `/commodity/` redirects to DEA commodity master; `/reports/` redirects to DEA reports hub; `/settings/profile/`, `/settings/billing/`, and `/settings/accounting/` redirect to existing workspace profile, selected-workspace billing, and DEA chart-of-accounts surfaces. Contact, settings roles, modules, numbering, and security remain absent. The next recommended action is either Phase 11.3 interim roles/numbering aliases or Phase 11.4 real modules/security screen design.
- SaaS IA Phase 11.3 interim workspace settings slug aliases are implemented. `/w/<workspace_slug>/settings/roles/` redirects to workspace team management, and `/settings/numbering/` redirects to Loans license/series setup. Settings modules and security remain absent until real workspace-owned screens exist. The next recommended action is Phase 11.4: design/implement modules and workspace security/audit settings screens before adding their slug aliases.
- SaaS IA Phase 11.4 workspace modules/security settings screens are implemented. `/workspace/<id>/settings/modules/` and `/workspace/<id>/settings/security/` are real workspace-owned settings pages; `/w/<workspace_slug>/settings/modules/` and `/settings/security/` redirect to them. Modules is a read-only installed-module map, and Security reads workspace `AuditLog` events instead of redirecting to account-level security. The next recommended action is a final Phase 11 route-map review, then customer/member portal IA.
- SaaS IA Phase 11 final review is complete in `docs/ui/workspace_slug_phase11_review.md`. The `/w/<workspace_slug>/...` tenant and workspace-settings route map is now live except Contact, which remains skipped in favor of Party, and the customer/member portal, which is a separate next phase.
- SaaS IA Phase 12.1 customer/member portal planning is complete in `docs/ui/customer_portal_phase12_plan.md`; the later Party Phase 10 runtime slice now supersedes its route-absent checkpoint.
- SaaS IA Phase 12.2 portal identity design is complete in `docs/ui/customer_portal_identity_phase12.md`. Portal access is Party-backed through explicit tenant `PartyPortalAccess`; matching email/phone is not authorization. `apps.tenant_apps.party.portal_access.resolve_portal_identity()` now resolves active grants for live tenant portal routes.
- SaaS IA Phase 12.3 portal selector contracts are implemented in [docs/ui/customer_portal_selector_contracts_phase12.md](ui/customer_portal_selector_contracts_phase12.md). `apps.tenant_apps.party.portal_selectors` validates `PortalIdentity` first, then returns Party-filtered dashboard, loan, invoice, payment, document, and statement summaries.
- SaaS IA Phase 12.4 customer portal shell/navigation is complete in [docs/ui/customer_portal_shell_phase12.md](ui/customer_portal_shell_phase12.md). `base_customer_portal.html` now has a portal-only topbar, enabled tenant portal navigation, `portal_content`, and `css/customer_portal.css`; tenant `/portal/...` routes are live, and public `/portal/...` remains absent.
- SaaS IA Phase 13.1 tenant route canonicalization baseline is complete in [docs/ui/tenant_route_canonicalization_phase13_plan.md](ui/tenant_route_canonicalization_phase13_plan.md). The plan corrects the route-map interpretation: Phase 11 completed route availability, not full canonical replacement. The next recommended action is Phase 13.2: convert remaining visible sidebar/dashboard top-level tenant links to existing slug aliases while keeping legacy tenant roots active.
- SaaS IA Phase 12 closeout in [docs/ui/customer_portal_phase12_review.md](ui/customer_portal_phase12_review.md) is superseded by the Party Phase 10 read-only portal MVP: tenant `/portal/...` routes now require active `PartyPortalAccess`, database-backed identity lookup, implemented Party-scoped selectors, and cross-party denial tests.
- SaaS IA Phase 13.2 tenant visible entry-link canonicalization is complete. Tenant sidebar Business Events, Financial Reports, and Commodity Master now point to `/w/<workspace_slug>/operations/`, `/reports/`, and `/commodity/`; the workspace dashboard DEA Dashboard quick action points to `/w/<workspace_slug>/accounting/`. Legacy tenant roots remain active. The next recommended action is Phase 13.3: direct-render slug entry wrappers for low-risk module entrypoints.
- SaaS IA Phase 13.3 has started with Parties. `/w/<workspace_slug>/parties/` direct-renders the existing Party list view while preserving the slug URL and Party's current authorization/query behavior.
- SaaS IA Phase 13.3 inventory slice is complete. `/w/<workspace_slug>/inventory/` direct-renders the existing Product home view while preserving the slug URL; detailed Product routes keep their existing action guards.
- SaaS IA Phase 13.3 loans slice is complete. `/w/<workspace_slug>/loans/` direct-renders the existing Girvi dashboard while preserving the slug URL and Girvi workspace access guard.
- SaaS IA Phase 13.3 accounting slice is complete. `/w/<workspace_slug>/accounting/` now direct-renders the existing DEA home view while preserving the slug URL. Phase 13.3 is complete for the low-risk top-level entrypoint set: parties, inventory, loans, and accounting. DEA operations/sales/purchase/commodity/reports and deep app routes remain compatibility redirects or legacy routes. The next recommended action is Phase 13.4 deep-link canonicalization planning.
- SaaS IA Phase 13.4 deep-link canonicalization planning is complete in [docs/ui/tenant_deep_link_canonicalization_phase13_4_plan.md](ui/tenant_deep_link_canonicalization_phase13_4_plan.md). The plan keeps nested app remounting and legacy-root removal out of scope, recommends Party first, then Product/Inventory, Rates, Notify, Data Tools, Girvi, and DEA, and defines tests required before Phase 13.5. The next recommended action is Phase 13.5a: Party read-only deep aliases as redirects first.
- SaaS IA Phase 13 is complete in [docs/ui/tenant_route_canonicalization_phase13_review.md](ui/tenant_route_canonicalization_phase13_review.md). Phase 13.5a added Party read-only deep aliases as redirects for create, detail, edit, and merge. Nested Party mutation aliases, Party direct-render deep aliases, internal link migration, Product/Inventory, Rates, Notify, Data Tools, Girvi, DEA, and legacy-root removal are deferred to the next route-canonicalization phase.
- SaaS IA Phase 14.1 has started in [docs/ui/tenant_party_deep_link_canonicalization_phase14.md](ui/tenant_party_deep_link_canonicalization_phase14.md). Party read-only deep aliases for create, detail, edit, and merge now direct-render the existing Party views after workspace slug validation, preserving Party's current action permissions. Party internal links, successful form redirects, nested mutation aliases, and legacy-root removal remain deferred.
- SaaS IA Phase 14.2 low-risk deep-link canonicalization is complete. Visible Party GET links prefer slug routes when `user_workspace` is available, and read-only aliases are live for Product/Inventory products, stock, stock audit, transactions, statements; Rates and rate sources; Notify notifications and notice groups; and Data Tools export. Product/Rates/Notify/Data Tools mutation routes, nested Party mutations, and Party success redirects remain legacy-only. The next recommended action is the compressed Girvi/Loans phase.
- SaaS IA Phase 15 compressed Girvi/Loans route canonicalization is complete in [docs/ui/tenant_girvi_route_canonicalization_phase15.md](ui/tenant_girvi_route_canonicalization_phase15.md). Read-only loan list/detail/tab/PDF/report aliases are live under `/w/<workspace_slug>/loans/...`, while loan create/update/delete, repayment, release, custody, lifecycle transition, operations-console retry, and document/template/storage mutations remain legacy-only. The next recommended action is the compressed DEA/Accounting read-only alias phase.
- SaaS IA Phase 16 compressed DEA/Accounting route canonicalization is complete in [docs/ui/tenant_dea_route_canonicalization_phase16.md](ui/tenant_dea_route_canonicalization_phase16.md). Top-level operations/sales/purchase/commodity/reports slug aliases now direct-render existing DEA views, and read-only aliases are live for chart/accounts/ledgers/transactions/reports/vouchers/payments/expenses/journal-entry-vouchers/periods/reconciliation/commodity details. Posting, business-event confirm, period mutation, reconciliation import/match, opening balance, commodity setup, and other DEA mutation routes remain legacy-only. The next recommended action is a final legacy-root compatibility policy phase.
- SaaS IA Phase 17 legacy-root compatibility closeout is complete in [docs/ui/tenant_legacy_root_compatibility_phase17.md](ui/tenant_legacy_root_compatibility_phase17.md). Legacy roots remain active compatibility routes while `/w/<workspace_slug>/...` is the preferred read-only/navigation surface where aliases exist. The compressed route-canonicalization work is complete; remaining route work is module-specific POST/HTMX/success-redirect migration or customer portal runtime access, not a blanket legacy-root redirect.
- Party portal domain strategy is now explicit for the MVP: keep customer portal access tenant-path only under `/portal/...`. Branded portal subdomains or public-schema portal entrypoints are deferred until the read-only portal has real users and the invitation/customer-auth lifecycle is stable. Existing `PartyPortalAccess` grants now have service-owned activate, suspend, and revoke transitions with public workspace audit events.
- Party model schema reference is now available in [docs/domain/party-model-schema.md](domain/party-model-schema.md), documenting all current `party` app models in one copyable markdown file.
- Girvi refactor plan refresh is complete in [docs/apps/girvi/refactor-plan.md](apps/girvi/refactor-plan.md). The document now treats P0-P5 as closed for the original stabilization scope, keeps P6 as the active local URL/template cleanup track, marks P7 event-driven DEA cutover as paused pending an explicit unpause, and points release/accrual hardening, Party rollout, and centralized preferences to their active plans instead of duplicating stale work.
- Girvi numbering direction is accepted in [docs/adr/2026-07-05-girvi-series-number-sequence.md](adr/2026-07-05-girvi-series-number-sequence.md), with rollout planned in [docs/plans/girvi-number-sequence-migration-plan.md](plans/girvi-number-sequence-migration-plan.md). Keep `License -> Series -> Loan/Release`, but move generated ID allocation to locked series-scoped sequence rows by document kind (`GIVEN_LOAN`, `TAKEN_LOAN`, `GIVEN_LOAN_RELEASE`, `TAKEN_LOAN_SETTLEMENT`). Runtime behavior is unchanged until the migration plan is implemented.
- Girvi audit follow-up stabilization has started: `GirviNumberSequence` tenant migration `0028` adds locked per-series/per-document numbering, generated Given/Taken loan and Given release IDs now allocate through sequence rows, previews are non-consuming, and `sync_girvi_number_sequences --dry-run/--apply` backfills next numbers from existing documents without renumbering old IDs. Tenant rollout must use `migrate_schemas`.
- Girvi sequence setup no longer blocks first loan creation when rows are missing: generated ID preview/allocation now initializes the relevant `GirviNumberSequence` from existing document IDs, and Series detail exposes sequence status plus a controlled "Sync Sequences" action for all document kinds in that series.
- Girvi repayment idempotency is now service-owned for blank references: repayment forms carry a hidden idempotency key, Given/Taken repayment services derive deterministic `REPAYMENT-*` markers for duplicate-submit protection, and the reconciliation report flags duplicate repayment references plus posted repayments missing markers.
- Girvi release/accrual hardening R4-R5 is implemented in [docs/plans/girvi-release-accrual-hardening.md](plans/girvi-release-accrual-hardening.md). Final release execution now snapshots settlement basis on `Release`, prefers posted accrual-row interest through release date when available, falls back to selector compatibility when needed, and extends the existing reconciliation report with release integrity mismatch categories.
- Girvi release final-settlement path is active: release no longer requires prepayment when final dues remain; the release workflow can calculate the settlement, post the final receipt, then complete closure. Generic closure without settlement remains blocked, and non-cash closure categories now go through a fail-closed `SettlementAdjustmentService` boundary until write-off/waiver/discount/correction documents and DEA posting are implemented.
- Girvi workflow documentation now includes an illustrated release/accrual settlement example in [docs/apps/girvi/workflows.md](apps/girvi/workflows.md), showing selector preview, catch-up accrual rows, release snapshot values, DEA receipt posting, fallback behavior, and reconciliation checks.
- Loans rewrite Step 1 is documented in [docs/plans/loans-rewrite-roadmap.md](plans/loans-rewrite-roadmap.md). This is a documentation-only baseline for a future side-by-side `apps.tenant_apps.loans` module; existing `girvi` remains the active runtime, and no schema, settings, URL, Python runtime, or migration behavior changed in this slice.
- Loans rewrite naming is now explicit in [docs/plans/loans-rewrite-roadmap.md](plans/loans-rewrite-roadmap.md): the replacement app should use `PawnLoan` for customer pawn/gold loans and `FundingLoan` for lender/repledge funding loans instead of collapsing both workflows into one over-generic `Loan` model.
- Loans rewrite architecture clarification is now recorded in [docs/plans/loans-rewrite-roadmap.md](plans/loans-rewrite-roadmap.md): workspace regulatory licenses own bounded pawn-loan/release series; loan policy is snapshotted at disbursal; repayment, accrual, partial-release LTV, closure, strict reversal, and durable DEA outbox rules are explicit; the MVP is PawnLoan-first; legacy Girvi services its own active loans; and unified source-labelled reads cover coexistence.
- Loans rewrite execution hardening is complete in [docs/plans/loans-rewrite-roadmap.md](plans/loans-rewrite-roadmap.md) and [ADR 2026-07-15](adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md). The authoritative `E0-E7` order now places policy contracts, license/series setup, durable outbox, DEA readiness, reversals, release/custody, operational proof, unified reads, and feature-gated cutover before production enablement. The plan is ready to begin `E1.1` as a separate implementation slice.
- Loans rewrite `E1.1` is complete: `apps.tenant_apps.loans` now has an unregistered, model-free package skeleton for domain, models, services, selectors, integrations, management commands, and tests. `LoansConfig` imports without Django setup or database access; no settings, URL, migration, or runtime behavior changed. The next executable slice is `E1.2`.
- Loans rewrite `E1.2` is complete: `LoansConfig` is registered in `TENANT_APPS` without URLs, admin, permissions, models, or migrations. Focused smoke coverage verifies app-registry identity, tenant-app membership, an empty model registry, and `makemigrations loans --check --dry-run` stability. The next executable slice is `E1.3`.
- Loans rewrite `E1.3` is complete: database-free domain modules define stored PawnLoan lifecycle states and their complete transition matrix, derived operational states, transaction/event kinds, custody, document, posting, and reversal vocabulary. Legacy Given/Taken names map explicitly to Pawn/Funding concepts, while FundingLoan vocabulary is marked post-MVP and runtime-disabled. The next executable slice is `E1.4`.
- Loans rewrite `E1.4` and the Phase 1 gate are complete: immutable pure-Python contracts define workspace policy defaults, optional license overrides, validation, deterministic resolution, and versioned disbursal snapshots for interest method, partial-month slabs, capitalization interval, cash/accrual recognition, valuation, maximum LTV, and per-period currency rounding. The next executable slice is `E2.1`, which introduces the first Loans tenant schema and must use `migrate_schemas`.
- Loans rewrite `E2.1` is complete: tenant migration `loans.0001_initial` adds `LoanLicense`, `LoanSeries`, `LoanNumberSequence`, `PawnLoan`, `PawnCollateralItem`, `LoanPolicySnapshot`, and `LoanChangeLog` with protected source relationships, explicit workspace ownership, bounded uniqueness/check constraints, active-tenant validation, and Party-backed borrowers. The migration was applied across local schemas with `migrate_schemas`; tenant-schema model/isolation coverage passes. No Loans route or UI uses the models yet. The next executable slice is `E2.2`.

- Loans operational parity OP6 is complete: canonical tenant-scoped selectors now drive the active, daily disbursal/repayment, interest due, overdue, release/renewal, storage inventory, license-expiry, and Loans-owned Party statement screens and CSV/XLSX/PDF output. Fixed loan tickets now render signed Original and Duplicate pages with one verification identity; existing repayment, release/Form H equivalent, renewal, notice, and license-register documents satisfy the accepted pilot boundary. The next Loans action is the operator parity pilot.

- LPD7's logical-layout/physical-print-profile architecture is committed but runtime implementation remains deferred. A pre-pilot compatibility guard now flags any active configured loan-ticket assignment that omits Original or Duplicate; the fixed fallback is compliant. The `jcl1` preflight has zero document-integrity findings after safely revalidating one unassigned pre-schema-change draft. The remaining document gate is the real A4/A5/simplex/duplex printer matrix.

- Girvi/Loans operator parity-pilot preparation has started with a concrete 12-scenario runbook and weighted scorecard. The `jcl1` baseline contains 8 Loans PawnLoans and 8 Girvi GivenLoans, uses explicit `DEFERRED` accounting, has zero document-integrity findings, and has no storage/verification/operational-notice evidence yet. The official score is not running because current accounting/Girvi runtime changes are uncommitted. A 191-test combined gate exceeded both five- and ten-minute limits and exposed an implicit-DEA test assumption; that focused test passes once DEA is selected explicitly. Migration-drift checks for DEA, Loans, and Girvi are clean. Consolidate the runtime checkpoint and run smaller completed product gates before operator scoring.

## Known Pressure Points

- A deep Loans architecture review is recorded in [docs/implementation/loans-deep-architectural-review.md](implementation/loans-deep-architectural-review.md). The PawnLoan service/selector/outbox architecture is fundamentally sound, but production hardening must database-enforce finalized loan/collateral/accounting-event immutability, gate or account for FundingLoan, prevent accidental production use of DEFERRED accounting, and recover stale PROCESSING outboxes. The recommended next slice is a documentation-and-test-first Loans truth-preservation hardening phase; no runtime behavior changed in this review.

- Settings and configuration architecture has been audited in
  [docs/implementation/settings-configuration-architecture-audit.md](implementation/settings-configuration-architecture-audit.md).
  The recommended direction is to narrow `django-dynamic-preferences` to
  lightweight UI/control-plane use, move business-critical policy to typed
  tenant-domain models, add public membership-scoped UI preferences, and retire
  duplicate central/legacy registrations through characterized phased cutovers.
  No runtime configuration or schema behavior changed in this documentation-only
  pass.

- PawnLoan risk communication is now operationally auditable for the manual
  email-first pilot. Risk alerts show email readiness/blockers, Operations
  Console reports real-versus-simulated provider readiness, and the notice
  ledger exposes source risk, template, consent snapshot, artifact, attempt,
  failure, and provider evidence. SMS/WhatsApp and configurable automation remain
  disabled pending their provider callback and policy controls.
- The controlled email pilot now has a stale-preview guard and tenant command
  `check_pawn_risk_email_pilot`. It fails closed for simulated providers or
  missing/mismatched consent, preview, and rendered-artifact evidence. A real
  provider and operator inbox success/failure-retry exercise are still external
  acceptance steps; credentials are intentionally not stored in Loans.
- Twilio integration is removed from active runtime and configuration. Notify
  v2 sends WhatsApp only through Meta Cloud API; SMS fails closed with no
  provider, and archived Twilio documentation remains historical only. WhatsApp
  production acceptance still requires secure callbacks and reconciliation.
- WhatsApp Cloud callback safety is implemented: HMAC and phone identity checks,
  tenant-only routing, replay-safe receipt evidence, unique provider-message
  routing, template-only dispatch, admin/settings diagnostics, and the
  `check_whatsapp_cloud_readiness` tenant gate. Real Meta configuration and an
  operator delivery/callback exercise remain external acceptance work.
- Manual PawnLoan risk communication now offers WhatsApp beside email for DPD
  and maturity alerts. It reuses locked revalidation and fingerprinted frozen
  economics, adds approved structured Cloud-template preview/evidence, enforces
  WhatsApp consent/contact/provider readiness, and preserves channel-specific
  dedupe. Automation, fallback, and bulk sending remain disabled.
- WhatsApp risk pilot acceptance is now visible from the Loans Operations
  Console and available through `check_pawn_risk_whatsapp_pilot`. It reconciles
  notice intent, Notify submission, ordered authenticated Meta receipts,
  delivered/read/failed state, timing, duplicates, unknown callbacks, and
  unresolved work. Real-message operator acceptance remains pending.

- PawnLoan risk-monitoring refresh now returns a `204 HX-Redirect` response for
  HTMX requests, so batch and individual refresh actions reliably reload the
  snapshot portfolio. Ordinary form posts retain their normal `302` redirect.
- PawnLoan batch risk selection excludes already-current assessments through a
  snapshot loan-ID subquery. This keeps PostgreSQL's `FOR UPDATE SKIP LOCKED`
  on PawnLoan rows only and avoids the unsupported nullable-outer-join lock.

- Tenancy architecture review is now documented in [docs/implementation/tenancy-architecture-audit-rls-vs-django-tenants.md](implementation/tenancy-architecture-audit-rls-vs-django-tenants.md). The recommendation is to prepare a hybrid migration and switch to shared-schema PostgreSQL RLS later: keep `django-tenants` operational for now, add explicit workspace ownership to tenant-owned models, separate product workspace slug from `Company.schema_name`, and only remove schema tenancy after constraints, reports, jobs, and isolation tests are RLS-ready.
- Public, global, and tenant UI boundaries remain mixed at the URL/template level. `shared_urlpatterns` are loaded in both public and tenant URLConfs, selected workspace profile fallback can make global routes behave tenant-aware, and subscription views contain company-vs-user ownership inconsistencies documented in [docs/ui/saas_information_architecture_audit.md](ui/saas_information_architecture_audit.md).
- An accepted ADR now defines the boundary between Girvi release, collateral custody handoff, and interest accrual catch-up at [docs/adr/2026-06-27-girvi-release-accrual-lifecycle-boundary.md](docs/adr/2026-06-27-girvi-release-accrual-lifecycle-boundary.md). R1-R5 are implemented for the current planned scope; remaining risk is tenant-level end-to-end validation with real DEA posting/accrual data.
- MVP cleanup audit has started in [plans/mvp-cleanup-audit.md](plans/mvp-cleanup-audit.md). The experimental sales/purchase/approval runtime apps have been removed under the no-production-data cleanup decision; Girvi cleanup is now proceeding in small verified stabilization slices.
- Girvi lifecycle compatibility aliases should be kept until old bookmarked transition URLs and legacy imported status values are no longer needed.
- Girvi custody database FKs now have a guarded migration from legacy `"girvi.Loan"` references to `TakenLoan`; tenant rollout should use `migrate_schemas`. Legacy command lifecycle is now documented in `docs/implementation/girvi-legacy-command-lifecycle.md`, and broader legacy-import guardrails now include command-boundary checks (only `missingcol.py` may import deprecated legacy loan models; runtime modules must not import legacy manual commands).
- Event-driven Girvi-to-DEA posting architecture remains accepted direction, but execution is currently paused.
- Some archived docs contain older naming, model shapes, and implementation assumptions.
- More cross-app reads should be audited and moved behind facades/selectors.
- Period-lock validation should remain inside the posting engine for all accounting paths.
- Orgs service extraction is started but not complete; workspace/team mutation views should continue moving toward thin request/response coordinators.
- Party rollout follow-up is now module-specific Party-first create/edit cutovers as workflows are prioritized; approval Party migration remains intentionally skipped for now.
- Girvi Phase 1 remaining hardening items need separate design/test setup before implementation: true cross-tenant integration tests are still missing, durable notice/audit timelines require schema decisions, and broader workflow UI idempotency should be added only where concrete duplicate-submit risk is identified.
- Deferred follow-up (shelved): add explicit `LoanChangeLog` entries for each Operations Console outbox retry action (previous Option 2). Current retry is controlled and permission-gated, but retry-attempt audit event emission is postponed for a later slice.
Historical assessments are preserved in [archive/root](archive/root/).
