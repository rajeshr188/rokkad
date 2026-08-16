---
status: active
owner: project
updated: 2026-08-16
tags: [contact, girvi, notify, notify-v2, party, loans, dea, retirement, migration]
related:
  - ../adr/2026-08-16-retire-contact-girvi-and-legacy-notify.md
  - ../adr/2026-06-18-party-domain-model.md
  - ../adr/2026-08-14-legacy-notify-retirement-boundary.md
  - party-rollout.md
  - legacy-notify-to-notify-v2-retirement.md
---

# Contact, Girvi, And Legacy Notify Retirement Plan

## Current Execution State

- Phase 0: complete on 2026-08-16.
- Phases 1-6 runtime retirement: substantially complete on 2026-08-16;
  Contact remains installed only for its historical migration graph.
- Phase 7: active. The recommended clean development baseline strategy is
  accepted. A verified pre-cutover PostgreSQL custom archive exists at
  `.local-backups/fresh_clean-pre-contact-baseline-20260816-154116.dump`.
- Do not delete/regenerate migrations mechanically: surviving histories contain
  required SQL views, database guards, seeds, repairs, and data transformations
  that must be carried into explicit current-state baseline operations.
- Baseline evidence: [Phase 0 inventory](../implementation/contact-girvi-notify-retirement-phase0-inventory.md).

## Objective

Remove the `contact`, `girvi`, and legacy `notify` applications without breaking
surviving Party, Loans, Notify v2, DEA, workspace, onboarding, or reporting
behavior.

The final repository must have no runtime, settings, URL, template, seed,
permission, test, or migration-graph requirement for the retired apps.
`notify_v2` remains active and generic.

## Execution Rules

1. Work dependency-first; delete an app only after its consumers are gone.
2. Keep each phase independently runnable and reviewable.
3. Add characterization tests before changing shared behavior.
4. Do not dual-write between legacy and target models.
5. Do not mutate posted vouchers or journal entries.
6. Do not use silent import fallbacks to hide incomplete removal.
7. Run the phase gate before starting the next phase.
8. Keep migration-history cleanup separate from runtime decoupling.
9. Stop before destructive database work unless the clean-reset policy is
   explicitly accepted.

## Target State

| Area | Retire | Retain |
| --- | --- | --- |
| Identity | Contact | Party |
| Loan operations | Girvi | Loans |
| Notifications | Legacy Notify | Notify v2 |
| Accounting | Girvi-specific DEA behavior | Generic DEA kernel |

## Phase 0 — Baseline, Decisions, And Freeze

### Work

- Accept the retirement ADR and record the development database policy.
- Inventory imports, model relations, generic relations, URLs, templates,
  permissions, seeds, jobs, management commands, fixtures, and tests for all
  three retiring apps.
- Classify every Girvi capability as `LOANS`, `RETIRE`, or `BLOCKED`.
- Classify every Contact field/relationship as `PARTY`, `DROP`, or `BLOCKED`.
- Classify legacy Notify data as `NOTIFY_V2`, `ARCHIVE`, or `DROP`.
- Capture baseline Django checks, migration plan, focused app tests, and full
  suite results. Record pre-existing failures separately.
- Freeze new features in Contact, Girvi, and legacy Notify.
- Disable scheduled Girvi accrual/reminder jobs and legacy Notify writes through
  normal configuration before code deletion.

### Gate

- No unclassified model, consumer, job, or operator workflow remains.
- The owner has resolved TakenLoan/funding/repledging disposition.
- Baseline failures and required test commands are recorded.
- No implementation begins while the retirement ADR is merely proposed.

### Rollback

Documentation and configuration only; re-enable frozen jobs if execution is
cancelled.

## Phase 1 — Complete Party Replacement Of Contact

### Work

- Inventory every foreign key, generic relation, form field, serializer,
  selector, report, template, and test using `contact.Customer`.
- Backfill and reconcile Party identity, roles, addresses, contact methods, tax
  identifiers, portal linkage, and DEA party-account resolution.
- Change surviving applications to store/query Party directly.
- Remove Customer fallbacks from account resolution only after parity passes.
- Replace Contact routes and UI with Party-owned equivalents where the feature
  survives; delete actions that existed only for Girvi.
- Stop Contact writes, then remove Contact models, admin, routes, templates,
  seeds, fixtures, commands, and tests.

### Gate

- No production import of `apps.tenant_apps.contact` remains.
- No surviving model points to a Contact model.
- Party reconciliation has zero unexplained identity, role, or account-link
  differences.
- Sales, Purchase, Expenses, Loans, Party portal, and DEA account-resolution
  tests pass using Party only.

### Rollback

Retain the nullable bridge and old Contact tables until the phase is accepted;
do not restore dual writes.

## Phase 2 — Remove Girvi Consumers From Surviving Apps

### Work

- Remove Girvi module cards, workspace aliases, proxy views, route guards,
  navigation links, and onboarding/setup-checklist entries.
- Remove Girvi permissions from role definitions and seed commands.
- Remove Girvi history and loan pages from Party; replace them with Loans-owned
  selectors only where equivalent product behavior is intended.
- Remove Girvi metrics/actions from dashboards and reports.
- Remove Girvi-specific configuration keys after any surviving value is moved
  to its target owner.
- Remove route-intent and UI tests for behavior intentionally retired; add
  negative tests proving removed routes do not resolve.

### Gate

- Outside the Girvi package and its historical migration/docs boundary, there
  are no Girvi model/view/facade imports.
- Django URL checks pass with Girvi URLs disabled.
- Orgs, Party, Onboarding, navigation, configuration, and dashboard suites pass.
- No user-facing action can create or mutate a Girvi record.

### Rollback

Re-enable route registration while the package still exists. Do not recreate
removed cross-app imports after the gate is accepted.

## Phase 3 — Clean Notify V2 And Retire Legacy Notify

### Work

- Keep Notify v2's generic event, policy, template, consent, delivery, provider,
  retry, and evidence behavior.
- Remove its Girvi reminder batch services, `GivenLoan` imports, Girvi PDF
  renderer, Girvi event defaults, seed data, templates, and tests.
- Move any surviving non-Girvi producer directly from legacy Notify to Notify
  v2 through its public service boundary.
- Remove shared authorization helpers or model reads that Notify v2 still takes
  from legacy Notify.
- Reconcile any legacy notification evidence that must survive; otherwise
  record it as development-reset data.
- Stop all legacy writes, remove legacy routes and seeds, and then remove the
  legacy Notify runtime package.

### Gate

- Notify v2 starts and passes tests with legacy Notify and Girvi uninstalled.
- No surviving app imports `apps.tenant_apps.notify`.
- No seed command creates legacy or Girvi-specific notification rows.
- Provider readiness, consent, dedupe, callback security, retries, and evidence
  tests remain green.

### Rollback

Keep legacy tables/package available but read-only until Notify v2 independence
is proven. Roll back callers, not data, if reconciliation fails.

## Phase 4 — Remove Girvi From DEA

### Work

- Add characterization tests for existing non-Girvi DEA posting, reversal,
  period-close, idempotency, and immutable-journal behavior.
- Remove Girvi imports from period-close and pre-close services.
- Remove `GIVENLOAN_*` and `TAKENLOAN_*` posting rules and required-rule entries.
- Remove Girvi voucher-type seeding from current default seed services.
- Remove `PaymentVoucher.create_release`, loan-model detection, `source_loan`,
  and Girvi-specific rule derivation after verifying no surviving source uses
  them.
- Retain generic principal/interest/fee or source-document fields only when a
  surviving application uses them.
- Remove Girvi seed-parity and accounting-integration tests.
- Preserve posted journal immutability in any retained database. Historical
  voucher-type rows are not deleted until the database policy permits it.

### Gate

- DEA imports no Girvi module and contains no GivenLoan/TakenLoan model-name
  introspection.
- DEA runs with Girvi absent from `INSTALLED_APPS`.
- DEA migrations load without Girvi.
- Generic posting, reversal, period close, trial balance, and journal
  immutability tests pass.
- Loans accounting behavior, if enabled, uses its own explicit DEA boundary.

### Rollback

Restore rule registration while old source code still exists. Never repair a
failed cutover by modifying posted journal rows.

## Phase 5 — Isolate And Delete Girvi Runtime

### Work

- Stop all Girvi jobs and management commands.
- Remove Girvi URL registration, settings entry, middleware prefixes, admin,
  templates, static assets, fixtures, and commands.
- Remove the Girvi package after static dependency checks show zero consumers.
- Remove obsolete Girvi-specific global templates and navigation fragments.
- Remove tests whose subject was intentionally retired; retain negative
  dependency and route tests.

### Gate

- Django system checks and URL loading pass with the package physically absent.
- Static search finds no active import, model lookup, URL namespace, permission,
  seed, template include, or scheduled task referencing Girvi.
- Party, Loans, Notify v2, DEA, Orgs, Onboarding, and configuration gates pass.

### Rollback

Restore the package and settings entry from the preceding commit. Database
tables remain untouched in this phase.

## Phase 6 — Remove Contact And Legacy Notify Runtime

### Work

- Repeat the physical-absence gate for Contact and legacy Notify.
- Remove settings registrations, URLs, middleware rules, admin registrations,
  templates, static assets, fixtures, commands, and packages.
- Remove obsolete permissions and default rows through explicit cleanup
  migrations when retaining a database.

### Gate

- Django starts with all three retired packages physically absent.
- Party, Loans, Notify v2, and DEA focused suites pass.
- Static searches find no active-code reference to the retired modules.

### Rollback

Restore only the failed package-removal commit; do not reintroduce runtime
consumers already migrated to target owners.

## Phase 7 — Migration Graph And Development Database Cutover

### Work

- Keep historical migration files during runtime decoupling so intermediate
  states remain loadable.
- Inventory surviving migrations that depend on retired app migration nodes.
- Choose one explicit final strategy:
  - **recommended development strategy:** create a clean migration baseline for
    surviving apps and rebuild the development database; or
  - **retained-data strategy:** keep tombstone migration packages until all
    dependencies and data-retention requirements are resolved.
- Never leave a migration dependency pointing to a deleted package.
- Recreate the database, run all migrations from empty, seed defaults, and run
  integrity checks under the intended database role.
- Verify that no retired tables, content types, permissions, or seed rows are
  created in the clean database.

### Carry-Forward Inventory

The clean baseline must preserve current-state behavior represented by custom
operations: DEA accounting masters, Party balance views, amount repairs, and
journal timestamp state; Loans funding/custody/intake/storage/media guards;
Product unified balance views and union constraints; Accounting posting,
reversal, and period guards; Orgs default roles and invitation normalization;
required Rates seed data; and Notify v2 Party recipient state.

Do not replay historical data-copy operations whose source columns or apps are
retired. Omit them when the initial schema embodies the result, or replace them
with an explicit current-state constraint/seed operation.

### Isolated Reference Database

`rokkad_baseline_rehearsal_20260816` is the guarded isolated reference database.
The current graph completed from empty for `public` and tenant schema
`baseline_tenant`. Tenant metrics are 193 base tables, 5 views, 63 user
triggers, and 2,880 constraints; public has 48 base tables and 435 constraints.
The graph creates six `contact_*` tables and no Girvi or legacy Notify tables.
`notify_v2_*` tables are retained and are not legacy Notify artifacts.

The replacement baseline must preserve required surviving schema behavior while
reducing the six Contact tables to zero.

### Replacement Baseline Result

Notify v2, Product, and DEA histories now create their current Party-owned
fields directly. Obsolete Customer/Contact bridge operations are retained only
as empty graph nodes so downstream migration names remain stable. DEA's custom
views, seeds, repairs, and database operations remain active.

Contact is removed from installed apps. The complete graph migrated from empty
in guarded database `rokkad_baseline_rehearsal_20260816_contactfree` for both
`public` and tenant `contactfree_tenant`. Django system checks and the complete
`makemigrations --check --dry-run` pass. The uninstalled Contact package is now
physically deleted and the 24-test retirement route suite passes. Party-native
conversion of stale surviving test fixtures plus final retired-artifact,
verification remain. Fresh-database ORM checks already confirm zero retired-app
ContentTypes and permissions in both public and tenant schemas.
The first Party-native fixture slice covers DEA fixed/unfixed purchase and sale
services. Remaining historical Contact imports are confined to sixteen test
modules; runtime code remains clean.

### Gate

- `makemigrations --check` reports no drift.
- The migration graph loads from an empty environment.
- Fresh migrate and seed complete without retired apps.
- No retired table or ContentType exists in the fresh database.
- Required uniqueness, foreign-key, workspace-isolation, and DEA integrity
  checks pass.

### Rollback

Preserve the pre-cutover database backup and preceding Git commit. Restore both
together; never run new code against an incompatible old migration graph.

## Phase 8 — Final Verification And Documentation Closure

### Work

- Run formatting/static checks, Django checks, migration checks, focused suites,
  and the complete test suite.
- Perform smoke tests for login, workspace selection, Party, Loans, Notify v2,
  DEA posting/reversal/period close, Sales, Purchase, and onboarding.
- Search code, templates, settings, fixtures, scripts, and tests for retired
  identifiers.
- Archive superseded Girvi/Contact/legacy-Notify operational documentation and
  update architecture, domain, status, roadmap, and agent memory.
- Mark the retirement ADR accepted and this plan completed only after every gate
  passes.

### Completion Criteria

- `contact`, `girvi`, and legacy `notify` packages do not exist.
- Their settings, routes, tables, permissions, ContentTypes, seeds, templates,
  jobs, commands, fixtures, and active documentation are gone.
- Notify v2 remains operational and contains no Girvi integration.
- Party is the only canonical counterparty model.
- Loans is the only pawn-loan operational app.
- DEA contains no Girvi-specific runtime behavior.
- A fresh database migrates and seeds successfully.
- The full test suite has no unexplained regression.

## Commit Boundaries

Use small, reversible commits rather than one deletion commit:

1. retirement inventory and characterization tests;
2. Party-only consumer migration;
3. Girvi external-consumer removal;
4. Notify v2 Girvi cleanup;
5. legacy Notify consumer and runtime removal;
6. DEA Girvi cleanup;
7. Girvi runtime removal;
8. Contact runtime removal;
9. migration baseline/database cutover;
10. final tests and documentation closure.
