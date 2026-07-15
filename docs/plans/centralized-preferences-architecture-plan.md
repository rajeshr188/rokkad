---
status: active
owner: project
updated: 2026-07-05
tags: [plans, configuration, preferences, django-dynamic-preferences]
related:
  - ../implementation/dynamic-preferences.md
  - ../STATUS.md
  - ../AGENT_MEMORY.md
  - ../constitution.md
---

# Centralized Preferences Architecture Plan

This plan tracks the migration from scattered `django-dynamic-preferences` usage to a centralized configuration architecture.

The goal is to separate platform defaults, workspace business policy, user UI preferences, subscription/plan configuration, normal domain state, and audit-critical snapshots without changing existing accounting, loan, inventory, or notification behavior accidentally.

## Current State

Phase 1-5 foundation and Girvi runtime read replacement are implemented. Phase 6 has started with Girvi snapshot coverage, Phase 7 has a central workspace UI route, and Phase 8 has explicit legacy Girvi write mappings. Phase 10 remains intentionally gated by cleanup evidence.

Completed:

- `apps.configuration` exists as the central configuration app.
- `WorkspacePreferenceModel` stores new workspace-scoped preferences through `django-dynamic-preferences`.
- `workspace_preferences_registry` is registered as the central workspace preference registry.
- `dynamic_preferences.users` is installed for user-scoped UI preferences.
- `apps.configuration.dynamic_preferences_registry` defines initial central preference keys for:
  - `platform`
  - `accounting`
  - `commodity`
  - `loan`
  - `inventory`
  - `notifications`
  - `documents`
  - `ui`
- `PreferenceService` is the central access boundary for new code.
- `PreferenceService` has an explicit user-override allowlist so user preferences cannot override accounting, posting, loan policy, ledger, currency, numbering, or notice behavior.
- `PreferenceAuditLog` records new service-layer writes.
- Focused service tests cover workspace reads/writes, fallback, user override allowlisting, workspace isolation, and audit logging.
- `CompanyPreferences` now resolves legacy Girvi preference keys through `PreferenceService.get_workspace_from_registry(...)`, preserving old storage/fallback behavior while placing the compatibility path behind the central service boundary.
- `apps.tenant_apps.girvi.service_modules.preferences` provides the Girvi runtime adapter over `PreferenceService` for current legacy loan defaults, interest rates, accrual policy, repayment/release/renewal catch-up policy, backfill policy, and disbursal deduction policy.
- The canonical workspace settings preferences route now renders the central workspace preference registry. The legacy Girvi preference page remains reachable separately for old keys.
- `migrate_preferences_to_workspace --dry-run` inventories legacy Girvi preference rows without writing central rows.
- `migrate_preferences_to_workspace --apply` writes explicitly mapped legacy Girvi rows to central lowercase `loan__...` workspace preference keys.
- Phase 6 snapshot tests now cover Girvi loan item interest-rate persistence and disbursal deduction component persistence so those historical values are not recomputed from mutable preferences.

Compatibility boundary:

- Girvi runtime modules should not call `apps.orgs.preferences.CompanyPreferences` directly.
- `CompanyPreferences` now delegates legacy registry resolution to `PreferenceService`.
- Existing Girvi preference keys such as `Loan__...` and `Interest_Rate__...` remain in the legacy orgs/Girvi registry for now.
- `CompanyPreferences` now reads through `company_preference_registry.manager(instance=...)` directly so the new central registry does not change legacy Girvi behavior by taking over `Company.preferences`.
- `CompanyPreferences` remains only as a compatibility facade and for compatibility tests until legacy storage is migrated or retired.

## Current Access Surfaces

Available now:

- New central preferences are available through `PreferenceService`.
- New central preference rows are visible in Django admin through `WorkspacePreferenceModel`.
- Canonical workspace settings preferences at `/workspace/<id>/settings/preferences/` edit central workspace preferences.
- Existing legacy workspace Preferences UI remains reachable and still edits legacy orgs/Girvi preferences.
- The dry-run migration inventory command is available as `python manage.py migrate_preferences_to_workspace --dry-run`.

Not available yet:

- Snapshot hardening for all preference-derived business defaults.
- Broader snapshot hardening for DEA/accounting defaults, document templates, and commodity/rate-derived business events.
- Retirement of compatibility code and legacy routes.

## Remaining Phases

### Phase 5: Runtime Read Replacement

Status: complete for current Girvi runtime reads.

Completed slice:

- Legacy `CompanyPreferences` resolution now goes through `PreferenceService.get_workspace_from_registry(...)`.
- Tests verify legacy workspace overrides, global fallback, and workspace scoping still work for Girvi keys.
- `views/loan.py` now resolves `Loan__Default_Date` and `Interest_Rate__...` through `apps.tenant_apps.girvi.service_modules.preferences`, which delegates to `PreferenceService` while preserving legacy key storage and defaults.
- Tests verify the Girvi adapter reads legacy workspace overrides and falls back per workspace for loan default date and default item interest rates.
- Girvi forms, repayment, release lifecycle, renewal, and scheduled accrual command policy reads now use the Girvi preference adapter rather than direct `CompanyPreferences` imports.
- Tests verify the adapter reads legacy workflow policy and disbursal policy overrides with per-workspace fallback.

Remaining work:

Replace non-Girvi module preference access in small, tested slices as those modules adopt the central registry. Accounting defaults and numbering policy still require DEA-specific snapshot tests before runtime replacement.

Rules:

- Do not rewrite domain workflows while replacing reads.
- Keep `CompanyPreferences` as a compatibility facade until all runtime consumers move.
- Prefer moving a single use case at a time from `CompanyPreferences` to explicit `PreferenceService` calls.
- Add tests around each replaced path before changing the next module.
- Preserve old key behavior with compatibility aliases or mapping during transition.

### Phase 6: Audit Snapshot Hardening

Status: started for Girvi loan/disbursal snapshots.

Ensure preferences affect new documents only and never reinterpret history.

Snapshot targets:

- Loan interest rate, interest method, grace period, and document policy at loan creation.
- Disbursal deduction policy decisions when disbursal is posted.
- Voucher number/prefix result on voucher creation.
- Selected ledger/account IDs in posting payloads and posted voucher/journal rows where relevant.
- Rate source and rate value used for commodity/inventory/business events.
- Document template/version used for generated legal or accounting documents.
- Posting rule/version metadata for journal-entry-producing workflows where needed.

Tests:

- Changing a workspace default does not mutate existing loans.
- Changing a default ledger does not mutate old voucher or journal rows.
- Changing a document template does not rewrite already generated document records.
- Changing rate source defaults does not reinterpret historical commodity movements or rate fixings.

Implemented slice:

- Loan creation persists the already-selected item interest rate and does not re-read mutable preferences while creating `LoanItem` rows.
- Disbursal transition persists deduction component amounts from the transition payload and does not re-read mutable preferences while saving historical component fields.

Remaining work:

- Add DEA/accounting default snapshot tests before migrating accounting defaults.
- Add generated document/template version snapshot tests before migrating document-template preferences.
- Add commodity/rate-source snapshot tests before migrating commodity/rate-derived defaults.

### Phase 7: Central Workspace Settings UI

Status: first central UI route implemented.

Build a real workspace preferences UI for the central architecture.

Sections:

- General
- Accounting
- Commodity/Metal
- Loan
- Inventory
- Notifications
- Documents
- UI Defaults

Access rules:

- Platform/global preferences: superadmin only.
- Workspace preferences: workspace Owner/Admin only.
- User preferences: current user only.
- Subscription/plan settings: platform/subscription system only, not workspace preferences.

Implementation direction:

- Use the existing workspace settings shell.
- Reuse `workspace_preferences_registry` and `workspace_preference_form_builder`.
- Keep the legacy Girvi preferences page reachable until all old keys are migrated or retired.
- Add permission and cross-workspace isolation tests for view access.

Implemented slice:

- `/workspace/<workspace_id>/settings/preferences/` renders central workspace preferences from `workspace_preferences_registry`.
- `/orgs/workspace/<workspace_id>/preferences/` remains the legacy Girvi/company preference page.
- Owner/Admin/superuser access is enforced for the central view; non-members receive 404.
- Tests cover owner access, non-member denial, and legacy route availability.

### Phase 8: Data Migration And Compatibility Mapping

Status: explicit legacy Girvi write mappings implemented.

Inventory and migrate existing preference rows only when their target scope is clear.

Existing legacy keys to map first:

- `Loan__Default_Date`
- `Loan__Interest_Deduction`
- `Loan__Haircut`
- `Loan__Accrual_Timing`
- `Loan__Auto_Post_Accruals`
- `Loan__Catchup_On_Receipt`
- `Loan__Catchup_On_Release`
- `Loan__Release_Fail_Closed_On_Accrual_Error`
- `Loan__Catchup_On_Renewal`
- `Loan__Allow_Backfill_Posting`
- `Loan__Disbursal_Deductions_Enabled`
- `Loan__Minimum_Document_Charge`
- `Interest_Rate__gold`
- `Interest_Rate__silver`
- `Interest_Rate__other`

Migration rules:

- Use a dry-run management command before writing rows.
- Do not blindly migrate all rows.
- Ignore or archive obsolete rows after they are proven unused.
- Move non-preference data to domain models instead of central preferences.
- Snapshot historical values only when safe and legally defensible.

Likely command:

```text
python manage.py migrate_preferences_to_workspace --dry-run
```

Implemented slice:

- `migrate_preferences_to_workspace --dry-run` reports matching legacy Girvi preference rows and writes nothing.
- `migrate_preferences_to_workspace --apply` writes explicitly mapped legacy Girvi rows into central `WorkspacePreferenceModel` rows.
- Tests cover dry-run no-write behavior, apply writes, and mutually exclusive `--dry-run`/`--apply`.

Current legacy-to-central key mappings:

- `Loan__Default_Date` -> `loan__default_date`
- `Loan__Interest_Deduction` -> `loan__interest_deduction_enabled`
- `Loan__Haircut` -> `loan__collateral_haircut_percent`
- `Loan__Accrual_Timing` -> `loan__accrual_timing`
- `Loan__Auto_Post_Accruals` -> `loan__auto_post_accruals`
- `Loan__Catchup_On_Receipt` -> `loan__catchup_on_receipt`
- `Loan__Catchup_On_Release` -> `loan__catchup_on_release`
- `Loan__Release_Fail_Closed_On_Accrual_Error` -> `loan__release_fail_closed_on_accrual_error`
- `Loan__Catchup_On_Renewal` -> `loan__catchup_on_renewal`
- `Loan__Allow_Backfill_Posting` -> `loan__allow_backfill_posting`
- `Loan__Disbursal_Deductions_Enabled` -> `loan__disbursal_deductions_enabled`
- `Loan__Minimum_Document_Charge` -> `loan__minimum_document_charge`
- `Interest_Rate__gold` -> `loan__default_gold_interest_rate`
- `Interest_Rate__silver` -> `loan__default_silver_interest_rate`
- `Interest_Rate__other` -> `loan__default_other_interest_rate`

### Phase 9: Expanded Tests

Status: expanded preference tests started.

Add broader coverage after runtime replacement starts.

Coverage targets:

- Global/platform defaults resolve correctly.
- Non-superusers cannot modify global preferences.
- Workspace preference reads/writes are scoped to the selected workspace.
- Workspace A cannot view or edit workspace B preferences.
- Missing workspace values fall back to platform defaults and then code defaults.
- Invalid keys are rejected or handled explicitly.
- Users can edit only their own UI preferences.
- User preferences do not override business-only workspace settings.
- Audit-critical documents retain snapshotted defaults after preference changes.
- Querysets and views enforce tenant/workspace filtering.

### Phase 10: Cleanup

Status: pending.

Remove compatibility code only after replacement and migration tests pass.

Cleanup targets:

- Retire `CompanyPreferences` once no runtime code depends on it.
- Remove duplicate legacy preference definitions.
- Remove direct raw dynamic-preferences manager calls from business modules.
- Remove or lock down the package-provided `/dynamic_preferences/` routes in production.
- Update workspace settings navigation to point to the central UI.
- Archive migration runbooks/results under `docs/archive/` after completion.

## Preference Taxonomy

Use preferences for:

- Platform defaults.
- Workspace business policy defaults.
- Module-specific workspace defaults.
- User UI and display preferences.

Use normal domain models for:

- Accounting periods.
- Voucher number sequences.
- Ledger/account records.
- Commodity/rate/fixing records.
- Notification templates and sent notification records.
- Subscription plans, subscriptions, invoices, payment history, and entitlements.

Use environment or secret storage for:

- Payment gateway credentials.
- WhatsApp/API credentials.
- SMTP credentials.
- Any token, key, password, or secret.

Use snapshots for:

- Posted voucher values.
- Journal entry values.
- Ledger transaction values.
- Historical metal rates used in posted documents.
- Loan terms after loan creation.
- Rate-fixing results.
- Generated legal/accounting document content and template version.
- Anything needed for audit, replay, legal proof, or historical correctness.

## Decisions Needed

- Whether the legacy Girvi preference UI should be merged into the central workspace settings page or kept as a separate compatibility page during migration.
- Whether accounting ledger defaults should remain string identifiers temporarily or become typed workspace configuration models with explicit FKs.
- Which Girvi preference keys should be renamed to lowercase central keys and which should remain compatibility aliases.
- Whether `/dynamic_preferences/` should be removed from all non-admin route surfaces or kept behind superuser-only access during rollout.
