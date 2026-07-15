---
status: active
owner: project
updated: 2026-07-04
tags: [cleanup, mvp, audit, legacy-import]
related: [../STATUS.md, ../AGENT_MEMORY.md, ../apps/girvi/refactor-plan.md, ../apps/dea/refactor-plan.md, party-rollout.md]
---

# MVP Cleanup Audit

## Goal

Prepare the current development branch to become the future MVP before importing legacy production data.

This report began as a cleanup audit. On 2026-06-19, the experimental `sales`, `purchase`, and `approval` runtime apps were explicitly approved for removal because there is no production data in those apps. This cleanup assumes a fresh dev database/schema reset, not an in-place production migration.

## Audit Rules

- Preserve anything needed for future legacy data import mapping.
- Keep the Party bridge and `contact.Customer` compatibility until Party Phase 9/cutover is complete.
- Keep migration history intact unless a no-production-data dev rebaseline is explicitly approved.
- Prefer removing or isolating disconnected runtime surfaces before model/table removal.
- Run checks/tests after every cleanup commit.
- When uncertain, mark code as risky or manual-decision, not unused.

## Evidence Checked

- `docs/AGENT_MEMORY.md`, `docs/STATUS.md`
- `docs/apps/girvi/*`, `docs/apps/dea/*`
- `django_project/settings/base.py`
- `django_project/tenant_urls.py`, `django_project/shared_urlpatterns.py`
- App `urls.py`, app configs, model/view/form/service/test files
- Template directories and URL references
- Static import/reference searches with `rg`
- Current git status, to avoid touching unrelated in-flight work

## Summary Classification

### Definitely Unused

These are absent from `TENANT_APPS`/`SHARED_APPS`, absent from root URL includes, and have no external references outside their own app folders.

- `apps/tenant_apps/savings_scheme/`
  - Not installed and not URL-included.
  - No external references found.
  - App config has stale `name = "savings_scheme"`.

### Probably Unused

These appear inactive or obsolete, but should get one focused verification commit before removal.

- `apps/tenant_apps/product/new_product.py`
  - Alternate normalized product design, not imported by active runtime.
  - Useful as design reference for future catalog normalization; archive/move before deletion.
- `apps/tenant_apps/product/0004_auto_views.py`
  - Stray app-root file outside migrations. The real migration exists at `apps/tenant_apps/product/migrations/0004_auto_views.py`.
  - Treat as probably unused, but verify no tooling imports it.
- `apps/tenant_apps/girvi/manager_improved.py`, `apps/tenant_apps/girvi/new_manager.py`, `apps/tenant_apps/girvi/managers.py`
  - Files self-label as deprecated/archived and point to `managers_refactored.py`.
  - Current `GivenLoan`/`TakenLoan` use `managers_refactored.py`.
  - Keep until import tests prove no active import path uses them.
- Duplicate template/tag modules:
  - `pages/templatetags/permissions.py`
  - `django_project/templatetags/permissions.py`
  - These look duplicated. Needs template load check before removal.

### Still Used

These are active despite looking legacy or transitional.

- `apps/tenant_apps/terms`
  - Tenant seed command still loads terms fixtures.
  - Tenant seed command still loads terms fixtures.
- `apps/tenant_apps/contact`
  - Still the compatibility source for `Customer`.
  - Required for Party bridge, import/export, Girvi borrower/lender FKs, and DEA account compatibility.
- `apps/tenant_apps/party`
  - Current strategic entity model.
  - Required for Phase 9 operational FK migration and legacy Customer mapping.
- `apps/tenant_apps/dea`
  - Accounting core. Keep posting engine, facade, voucher types, party account mapping, period checks, reports, and audit.
- `apps/tenant_apps/girvi`
  - Current loan domain. Active models are `GivenLoan` and `TakenLoan`.
  - Legacy compatibility remains necessary for old imported statuses, bridge migrations, and some admin/import/export surfaces.
- `apps/tenant_apps/product`
  - Active catalog, inventory, stock, pricing, and stock movement app.
- `apps/tenant_apps/rates`
  - Used by dashboard/navigation and operational rate reads.
- `apps/orgs`
  - Tenant/workspace core, membership, permission seed, tenant default seeding.
- `apps/onboarding`
  - Workspace provisioning and seed flow.
- `apps/subscriptions`
  - Billing/subscription flow and middleware context.
- `accounts`, `pages`, `django_project`
  - Shared auth/profile/public/tenant shell.

### Risky To Remove

- `apps/tenant_apps/notify`
  - Legacy notification app is still imported by Girvi notice/dashboard/print paths and tenant seed defaults.
  - `notify_v2` is the preferred target, but legacy notify cannot be removed until Girvi notice creation and seed defaults are cut over.
- `apps/tenant_apps/notify_v2`
  - Newer target and current navigation item. Keep.
- `apps/tenant_apps/dea/posting/legacy_direct_write_engine.py`
  - Documented as legacy compatibility, not target architecture.
  - Remove only after proving no caller needs direct-write parity for legacy import/reconciliation.
- Girvi legacy models in `apps/tenant_apps/girvi/models/loan.py`
  - Deprecated and no longer broad-exported from `models/__init__.py`.
  - Historical access must go through `models.legacy`.
  - Referenced by migrations, explicit legacy resources, and old management commands.
  - Model/table removal is a migration decision and not part of initial cleanup.
- `contact.Customer.account` compatibility alias
  - Explicitly required by Party rollout and DEA tests.
  - Do not remove before operational FKs move to Party.
- Contact import/export views/resources
  - Important for legacy production data import mapping; keep until the dedicated import pipeline exists.
- Root database dumps and rehearsal artifacts
  - `prod_full_2026-04-10.dump`, `rokkaddb_prod_full_2026-04-10.dump`, `rokkad_prod_rehearsal.sql`
  - Not app code, but likely relevant to legacy import work. Move/label only with owner approval.

### Removed Experimental Runtime

- `apps/tenant_apps/Chitfund/`
  - Removed on 2026-07-04 after confirming it was absent from `TENANT_APPS`/`SHARED_APPS`, not URL-included, and had no external runtime references.
  - Removed models were `Contact`, `Chit`, `Collection`, and `Allotment`.
  - The app had a stale app config path (`name = "Chitfund"`) and was not part of the current MVP architecture.
- `apps/tenant_apps/sales`, `apps/tenant_apps/purchase`, and `apps/tenant_apps/approval`
  - Removed from `TENANT_APPS`, tenant URLs, navigation, templates, and runtime references on 2026-06-19.
  - App migration histories were removed with the apps.
  - Product migration/model state was rebaselined to remove `purchase.PurchaseItem` foreign keys.
  - DEA `SalesInvoiceVoucher` and `PurchaseInvoiceVoucher` remain and are not part of this removal.
  - Future commerce/procurement/approval workflows should be rebuilt around commodity, inventory, settlement, and DEA posting boundaries.
- DEA overlapping dashboards/routes
  - `dea_home`, `dea_dashboard`, `dea_dashboard_legacy`, `dea_dashboard_enhanced`
  - Current docs identify overlap. Choose one MVP landing route before removing aliases.
- Product stock direct journal-entry paths
  - Routes such as direct stock-in and stock journal-entry flows exist.
  - Must align with DEA posting boundaries before removal.
- Girvi duplicate route aliases
  - Statement routes and storage-box routes have duplicate path/name aliases.
  - Keep bookmarked aliases until there is a compatibility window decision.
- Girvi background tasks
  - First cleanup slice completed on 2026-06-20: broken/dead notification task bodies now return an explicit disabled result instead of referencing stale names.
  - Next cleanup should decide whether scheduled registration should be removed entirely or replaced with notify_v2 reminder batches.
- Girvi custody/repledge
  - Repledge creation now resolves an active TakenLoan series before creating `TakenLoan`, and loan-id generation can sequence against the concrete loan model instead of always reading `GivenLoan`.
  - Runtime custody helpers no longer import legacy `models.loan` for collateral lookup or assume `loan.customer`; current borrower naming is used with compatibility fallback where needed.
  - Custody FKs now have a guarded migration from legacy `"girvi.Loan"` references to `TakenLoan`.
  - `RepledgedLoanItem` remains as readable compatibility data for import/backfill and old rows, but legacy create/update/delete routes are closed.
  - Focused coverage now protects repledge creation, return-all, TakenLoan close checks, and release blocking/return behavior.
  - Direct TakenLoan amount, weight, description, and current-value properties now read from `RepledgeHistory`.
  - TakenLoan principal queryset totals and itemwise amount annotations now read from `RepledgeHistory`.
  - TakenLoan weight/current-value queryset annotations now read from `RepledgeHistory`.
  - TakenLoan item-interest direct reads, interest-base queryset annotations, and selector totals now derive from `RepledgeHistory.repledged_amount` and `LoanItem.interestrate`.
  - Refactored loan interest metric annotations now use `calculated_*` names so evaluated querysets do not shadow read-only model properties.
  - P1 TakenLoan/custody migration cleanup is complete.
  - P2 canonical transition cleanup is complete: legacy primary state/UI/form transition metadata was moved out of primary registries and into explicit compatibility registries.
  - Canonical TakenLoan transition state/UI/form metadata now covers activate and settlement transitions.
  - Active loan detail, transition form, and unified loan list surfaces now render canonical lifecycle labels instead of raw legacy status values.
  - Flow-derived transition matrix tests now verify canonical registry metadata and documented source/target states against `flows.py`.
  - P3 has started: synchronous payment, posting, accrual, repayment view, and loan journal read paths now go through `apps.tenant_apps.girvi.integrations.dea_adapter`.
  - Model payment helper voucher creation now goes through `service_modules.payment_voucher_creation`; the old model methods remain compatibility wrappers.
  - Dashboard payment count reads now go through selectors and the DEA adapter instead of direct runtime `PaymentVoucher` lookup.
  - P3 is complete for current refactored runtime paths; deprecated `models/loan.py` direct DEA imports are deferred to P5 legacy model containment.
  - P4 has started: `loan_detail` display metrics, storage position lookup, interest reporting, and release CTA metadata now come from the detail read-model selector.
  - P4 repayment view-thinning is complete: GivenLoan receipt catch-up accrual, repayment payload shaping, posting delegation, TakenLoan repayment posting, and result-message construction now live in `service_modules.repayment`.
  - P4 is complete: bulk merge/delete selection parsing, guard validation, merge orchestration, delete orchestration, and structured operation errors now live in `service_modules.bulk_operations`.
  - P5 has started: deprecated `Loan` / `LoanPayment` are no longer broad exports from `apps.tenant_apps.girvi.models`; explicit historical access goes through `models.legacy`, and guard tests prevent new broad runtime imports.
  - Legacy payment import/export is explicitly named `LegacyLoanPaymentResource`; the old `LoanPaymentResource` name remains as a compatibility alias.
  - Legacy/manual management commands now have visible help labels, but the next cleanup should decide whether commands such as `do` and `missingcol` should be archived, disabled, or retained only for import/rehearsal operations.
- Girvi `resources.py`
  - Some resources are active via admin/exports.
  - Legacy payment import/export is explicitly named `LegacyLoanPaymentResource`.
  - Keep export classes needed for import mapping until the production import pipeline is designed and tested.
- `apps/tenant_apps/utils/loan_pdf.py`
  - Large legacy PDF helper still used by Girvi printing/notice paths.
  - Do not remove until template rendering and notify_v2 PDF generation fully replace it.
- `mt_enhancement_completed_phase/`
  - Looks like historical enhancement scripts. It is outside installed apps.
  - Move to `docs/archive/` or `scripts/archive/` only after confirming no local runbook depends on it.
- Root test/debug artifacts
  - `test_output.txt`, `transition_command_test_output.txt`, `tenant_admin_debug.txt`, `tenant_admin_src.txt`, `_check_ledger_cols.py`, `final_validation.py`, `test_refactor_integration.py`, `test_weight_annotations.py`
  - Need owner decision: archive as historical evidence, convert into real tests, or delete.

## App-by-App Notes

### accounts

- Still used: profile views, workspace switching, custom user/profile forms, allauth integration.
- Probably unused: none confirmed.
- Needs decision: `fetch_google_profile_pics` command if Google profile sync is not MVP.

### apps.onboarding

- Still used: onboarding URLs, workspace provisioning, tenant seed flow.
- Risky: seed/provisioning code touches tenant creation; test before any cleanup.
- Needs decision: tour/preferences depth for MVP.

### apps.orgs

- Still used: tenant model, domain model, workspace/membership/invitation, middleware, seed commands.
- Risky: seed commands also seed terms, notify, notify_v2, party roles, DEA ledgers.
- Cleanup direction: continue service extraction, but no removal before tenant provisioning tests pass.

### apps.subscriptions

- Still used: shared URL include, middleware context, plans/checkout/webhook/dashboard.
- Needs decision: whether billing is MVP-blocking or can be hidden while preserving data model.

### pages

- Still used: shared root/public pages and dashboard.
- Removed: MAXX bulk import helpers tied to experimental sales/purchase imports and fake gold-as-USD balances.

### approval

- Removed experimental runtime on 2026-06-19.
- Future approval/return workflows should be redesigned with inventory reservation/commodity movement semantics.

### Chitfund

- Removed on 2026-07-04 as an unused, non-installed tenant app.
- Future chitfund workflows, if revived, should be redesigned as a new Party/accounting-aware domain rather than restoring this disconnected app.

### contact

- Still used and strategic during bridge period.
- Risky: import/export and `Customer` fields are important for legacy data import mapping.
- Cleanup direction: freeze new feature work, route new external identity work to Party, keep compatibility.

### party

- Still used and current architecture.
- Cleanup direction: none now except keep tests and docs current.

### dea

- Still used and core.
- Risky/obsolete workflows:
  - direct-write legacy engine
  - voucher post/reverse logic outside the posting engine
  - overlapping dashboards
  - direct Contact/Product internals at boundaries
- Cleanup direction: refactor behind services/selectors first, then remove duplicate UI routes.

### girvi

- Still used and core.
- Risky/obsolete workflows:
  - legacy `Loan`/`LoanPayment`
  - deprecated managers
  - background notification tasks with stale names
  - model methods creating DEA payment vouchers
  - duplicate URL aliases
  - legacy import/export resources
- Cleanup direction: contain legacy exports, repair/disable broken tasks, route posting through one adapter, then clean duplicate routes.
- Recent cleanup: repledge creation now supplies the required series for `TakenLoan`; remaining custody cleanup is the legacy FK migration/containment.

### notify

- Risky to remove. Legacy but still runtime-referenced.
- Cleanup direction: migrate Girvi notice/print/dashboard paths to notify_v2, then freeze/remove routes.

### notify_v2

- Still used as target notification architecture.
- Cleanup direction: keep, expand adapters/events as replacement for legacy notify.

### product

- Still used.
- Probably unused: `new_product.py`, app-root `0004_auto_views.py`.
- Risky: stock/DEA journal-entry paths and old JSON/attribute transition artifacts.
- Cleanup direction: archive unused design file after preserving import-mapping notes. Product migration state was rebaselined only to remove deleted `purchase.PurchaseItem` references.

### purchase

- Removed experimental runtime on 2026-06-19.
- DEA `PurchaseInvoiceVoucher` remains.

### rates

- Still used.
- Cleanup direction: keep. Fixture seeding remains part of tenant defaults.

### sales

- Removed experimental runtime on 2026-06-19.
- DEA `SalesInvoiceVoucher` remains.

### terms

- Still used as reference/payment term app.
- Cleanup direction: keep despite no direct URL include.

### utils

- Still used: `loan_pdf.py` by Girvi/notify paths; HTMX helpers and crispy layout helper may be used by forms/views.
- Risky: `loan_pdf.py` is legacy-style but still operational.

## Duplicate Or Obsolete Workflows

- Party vs Contact:
  - Party is target; Contact/Customer is compatibility and import bridge.
  - Do not remove Contact before Party Phase 9/cutover.
- Notify vs Notify V2:
  - Notify V2 is target.
  - Legacy notify remains wired to Girvi.
- DEA dashboards:
  - Multiple dashboard/home routes need one MVP entry point.
- Girvi loan lifecycle:
  - Canonical states exist, but legacy aliases remain for compatibility.
- Girvi payment/posting:
  - Posting is split across views, services, model helpers, and DEA facade calls.
- Product stock posting:
  - Direct journal-entry stock paths should be reconciled with DEA posting boundaries.

## Safe Removal Plan In Small Commits

### Commit 1: Audit Guardrails Only

- Add this report.
- Add/adjust architecture tests that prove `savings_scheme` is not installed or URL-included.
- Run:
  - `python manage.py check`
  - focused architecture tests

### Commit 2: Quarantine Definitely Unused Apps

- `Chitfund` was removed on 2026-07-04.
- Move `savings_scheme` to an archive location or remove it from the runtime tree, without touching migrations for installed apps.
- If deleting app folders, first confirm no future legacy import mapping needs these models.
- Run:
  - `python manage.py check`
  - app registry/import tests

### Commit 3: Remove Stray Non-Runtime Files

- Remove or archive `apps/tenant_apps/product/0004_auto_views.py`.
- Move `product/new_product.py` design notes into `docs/archive/product/` or keep as a documented reference if future normalized attributes are planned.
- Run:
  - `python manage.py check`
  - `python manage.py test apps.tenant_apps.product`

### Commit 4: Girvi Broken Background Task Decision

- Completed first slice on 2026-06-20: disabled stale notification task bodies with focused guardrail tests.
- Remaining follow-up: decide whether to remove scheduled registration entirely or repair reminders into current `GivenLoan`/notify_v2 paths.
- Do not remove data models.
- Run:
  - `python manage.py test apps.tenant_apps.girvi.tests`

### Commit 5: Notify Cutover Prep

- Add notify_v2 replacement paths for any Girvi notice flow still using legacy notify.
- Keep legacy notify routes temporarily.
- Run:
  - `python manage.py test apps.tenant_apps.notify apps.tenant_apps.notify_v2 apps.tenant_apps.girvi.tests.test_print_service_orchestration`

### Commit 6: Route Alias Cleanup

- Remove only duplicate URL aliases that have agreed compatibility coverage.
- Keep redirects or aliases for bookmarked operational URLs until a cutoff date is chosen.
- Run route reverse tests and smoke tests for Girvi/DEA/Product.

### Commit 7: Legacy Runtime Containment

- Stop wildcard-exporting deprecated Girvi models if tests prove no active path requires implicit imports.
- Move legacy import/export resources behind explicit names.
- Add architecture tests preventing new imports of deprecated managers and legacy `Loan`.
- Run full targeted Girvi and DEA suites.

## Minimum Verification Matrix

After each cleanup commit:

- `python manage.py check`
- App-specific tests for the touched app
- Import/URL reverse smoke tests for affected routes

Before declaring MVP cleanup complete:

- Tenant seed command dry-run or tenant test setup
- Party bridge tests
- DEA posting tests
- Girvi lifecycle/payment/release tests
- DEA sales/purchase voucher posting tests
- Product inventory tests
- Notify/notify_v2 tests after notification cutover

## Current Recommendation

Continue with small verified cleanup slices. Do not remove Contact, legacy Girvi models, legacy notify, DEA compatibility engines, or import/export resources until the legacy production import mapping is designed and tested. Treat future sales/purchase/approval as a fresh domain redesign, not a resurrection of the removed experimental apps.
