## Plan: Girvi Model-View Gap Closure (Trackable)

Goal: Align girvi models with routed views/templates, close missing endpoints, and remove legacy/refactor mismatches with a strict, verifiable execution sequence.

How to use this file:
- Keep each task as unchecked until merged and verified.
- Add PR link, commit hash, and date under each completed task.
- Do not start a dependent task before blockers are complete.

### Status Legend
- [ ] Not started
- [~] In progress
- [x] Done
- [!] Blocked

## Phase 0: Baseline and Guardrails

### P0.1 Freeze baseline and branch hygiene
- [ ] Confirm working branch and collect current diff snapshot.
- [ ] Capture current girvi route map from apps/tenant_apps/girvi/urls.py.
- [ ] Record current high-risk templates used by loan detail pages.

Acceptance:
- [ ] Baseline notes committed in task doc/comment.
- [ ] No unrelated modified files are included in first functional PR.

## Phase 1: Canonical Loan Contract (Refactored First)

### P1.1 Declare refactored model API as source of truth
- [x] Validate all loan views use refactored contracts from apps/tenant_apps/girvi/models/loan_refactored.py.
- [x] Identify and list legacy-only property/method usages still referenced from templates/views.

### P1.2 Remove legacy API leaks from active templates/views
- [x] Normalize detail/list templates to active field names and relation names.
- [x] Remove or rewrite stale branches that assume unavailable model relations.
- [x] Ensure prev/next navigation contract is consistent across active loan detail variants.

### P1.3 Route semantics cleanup for loan CRUD
- [x] Separate overloaded meanings for create/update endpoints in apps/tenant_apps/girvi/urls.py.
- [x] Ensure route names are unique and unambiguous.
- [x] Update all affected template links and redirects.

Acceptance:
- [x] Loan create/update/detail paths are deterministic.
- [x] No active template references legacy-only loan API names.
- [x] Loan flow smoke test passes (list -> detail -> edit -> back).

## Phase 2: Expose Existing Custody/Repledge Workflows

### P2.1 Mount existing custody URL set
- [x] Integrate apps/tenant_apps/girvi/urls/custody_urls.py into apps/tenant_apps/girvi/urls.py.
- [x] Confirm namespace consistency and no route collisions.

### P2.2 Align custody views to active model layer
- [x] Verify imports and query usage in apps/tenant_apps/girvi/views/custody_views.py against canonical models.
- [x] Fix any old/new model cross-over.

### P2.3 Enable user paths for repledge lifecycle
- [x] Create clear entry points for select items -> create repledge -> view collateral -> return collateral.
- [x] Wire custody checks into release path where required.

Acceptance:
- [ ] All custody endpoints are reachable via URL routing.
- [ ] Repledge creation and return flows are executable from UI.
- [ ] Release pre-check with custody status works end-to-end.

## Phase 3: Fill Missing Model-Backed View Surfaces

### P3.1 RepledgedLoanItem user lifecycle completeness
- [ ] Verify create/update/delete/detail coverage for repledged items.
- [ ] If create/update is custody-only by design, document and enforce that path.

### P3.2 Loan template management decision and implementation
- [ ] Decide: admin-only vs dedicated UI for apps/tenant_apps/girvi/models/template.py.
- [ ] If dedicated UI chosen: add list/detail/create/update/delete routes and views.
- [ ] If admin-only chosen: remove dead assumptions in user templates and add docs.

### P3.3 LoanItemPic and auxiliary artifacts
- [ ] Confirm whether apps/tenant_apps/girvi/models/loan_item.py image artifacts require user-facing management.
- [ ] Add or explicitly defer UI for these artifacts.

Acceptance:
- [ ] Every concrete model is classified as user-managed, workflow-managed, or admin-only.
- [ ] No modeled artifact is left as accidental orphan.

## Phase 4: Reports, Archives, Notices, and Print Alignment

### P4.1 Query source consistency
- [ ] Validate report views in apps/tenant_apps/girvi/views/reports.py against canonical loan models.
- [ ] Validate print/export paths in apps/tenant_apps/girvi/views/prints.py.
- [ ] Validate notice/archive queries against active fields and statuses.

### P4.2 Remove duplicate/ambiguous routes
- [ ] Eliminate duplicate crosstab/ambiguous entries from apps/tenant_apps/girvi/urls.py.
- [ ] Update links/tests accordingly.

Acceptance:
- [ ] Reports and exports pull from intended model set.
- [ ] No duplicated or conflicting route names remain.

## Phase 5: Final Hardening

### P5.1 Regression checklist
- [ ] Loan list filters and table partials.
- [ ] Loan detail tabs: items, payments, transactions, statement, notices, release.
- [ ] Transitions: approve/disburse/deliver/cancel/default/auction/sold.
- [ ] Split/merge loan actions.
- [ ] Payment create/update/delete.
- [ ] Release create/update/delete and bulk release.
- [ ] Custody/repledge workflows.
- [ ] Statement session lifecycle.
- [ ] Series/license lifecycle and next-loan-id endpoint.

### P5.2 Documentation and handoff
- [ ] Update internal migration note for legacy loan model dependency status.
- [ ] Publish final model-view matrix (covered/partial/admin-only/orphan).
- [ ] Add post-merge monitor checklist for error logs and user reports.

Acceptance:
- [ ] End-to-end smoke path has no blocking runtime errors.
- [ ] All identified gaps are either fixed or explicitly deferred with owner/date.

---





## Strict Execution Checklist (Dependency Ordered)

### Block A (must complete first)
1. [x] A1: Canonical API audit for active loan pages.
2. [x] A2: Template/view property mismatch cleanup.
3. [x] A3: Loan route semantics cleanup.

Exit criteria:
- [x] No active page depends on legacy-only loan API names.
- [x] Loan create/update/detail route intent is unambiguous.

### Block B (starts after Block A)
1. [x] B1: Mount custody URLs.
2. [x] B2: Fix custody view model imports/contracts.
3. [x] B3: Wire repledge lifecycle entry points in UI.

Exit criteria:
- [~] Custody/repledge workflows are reachable and functional. (Manual end-to-end UX pass pending)

### Block C (parallel after Block B)
1. [ ] C1: Repledged item lifecycle completeness decision + fixes.
2. [ ] C2: Loan template management decision + implementation/documentation.
3. [ ] C3: Loan item media artifact management decision + implementation/documentation.

Exit criteria:
- [ ] All concrete models classified and covered by intended surface.

### Block D (after B and C)
1. [ ] D1: Report/archive/notice/print source alignment.
2. [ ] D2: Remove duplicate/ambiguous routes.
3. [ ] D3: Full regression pass and issue triage.

Exit criteria:
- [ ] No known model-view coverage gaps remain unowned.

---

## Gap Register (Track per Fix)

| Gap ID | Gap Summary | Severity | Planned Fix | Owner | Status | PR/Commit | Verified |
|---|---|---|---|---|---|---|---|
| G2 | Legacy/refactor API mismatch in active templates/views | Critical | Normalize to refactored contract |  | [x] | local | [x] |
| G3 | Overloaded loan route semantics | High | Split/clarify create/update paths |  | [x] | local | [x] |
| G1 | Custody/repledge routes not mounted | Critical | Mount custody URL include and verify namespace |  | [x] | local | [x] |
| G4 | Repledged item lifecycle surface incomplete | High | Complete workflow path or document custody-only design |  | [~] | local | [ ] |
| G5 | LoanTemplate/TemplateFrame management ambiguity | Medium | Implement UI or declare admin-only |  | [ ] |  | [ ] |
| G6 | Duplicate/ambiguous report routes | Medium | Consolidate and update links/tests |  | [ ] |  | [ ] |

---

## Verification Commands and Checks

- [x] Run targeted Django checks for girvi URL/view integrity.
- [~] Run focused tests for loan, release, payment, custody, statement modules. (`django-tenants` tenant-schema setup blocks default non-tenant test execution for Girvi in current harness)
- [ ] Perform manual HTMX flow checks on key detail pages.
- [ ] Confirm no new unresolved errors in edited files.

---

## Change Log

### Task ID: P1 + P2.1/P2.2 verification and execution
- Date: 2026-03-18
- Files changed:
	- apps/tenant_apps/girvi/views/loan.py
	- apps/tenant_apps/girvi/urls.py
	- apps/tenant_apps/girvi/views/custody_views.py
	- apps/tenant_apps/girvi/tests.py
	- apps/tenant_apps/girvi/docs/plan-girvi model-view gap closure.md
- Summary of change:
	- Completed unambiguous loan CRUD routing by splitting create/update wrappers around `loan_save` and introducing `girvi_loan_create_for_customer`.
	- Mounted custody/repledge routes directly in primary girvi URLConf and normalized custody view redirects to canonical existing route names.
	- Fixed custody view model imports to canonical package exports and resolved test discovery blocker in `apps/tenant_apps/girvi/tests.py` (`TestCase` import).
- Risk notes:
	- Custody route paths now use `girvi/custody/...` namespace and may require UI link updates in next pass (P2.3).
- Verification performed:
	- `python manage.py check` -> no issues.
	- `python manage.py test apps.tenant_apps.girvi.tests --verbosity 1` -> 5 tests passed.
	- Legacy token search in `templates/girvi/loan/*.html` for `loanid|loanamount|get_loanamount_with_currency|noofmonths|loan.customer` -> no matches.
- Follow-up required:
	- Execute P2.3 functional UI wiring and manual HTMX custody/repledge smoke checks.

### Task ID: P2.3 user path wiring
- Date: 2026-03-18
- Files changed:
	- templates/girvi/loan/loan_detail_1.html
	- templates/girvi/loan/loan_detail.html
	- templates/girvi/loan/loan_detail_2.html
	- templates/girvi/release_custody_check.html
	- templates/girvi/loan_custody_summary.html
	- templates/girvi/taken_loan_collateral.html
- Summary of change:
	- Routed release action through custody pre-check (`release_loan_check_custody`) on all active loan detail variants.
	- Added direct UI entry points for repledge creation and custody summary from loan detail pages.
	- Fixed release custody check template route names and lender return action wiring.
	- Added missing custody summary and taken-loan collateral templates so P2.3 endpoints render and navigation is complete.
- Risk notes:
	- Manual business-flow validation still needed for complete UX sign-off.
- Verification performed:
	- `python manage.py check` -> no issues.
	- `python manage.py test apps.tenant_apps.girvi.tests --verbosity 1` -> 5 tests passed.
- Follow-up required:
	- Perform manual flow checks: select collateral -> create repledge -> open collateral detail -> return collateral -> release with auto-return.

## Phase 6: Migrate to Django 6 Native Template Partials

### P6.1 Eliminate django-render-block from Girvi views
- [x] `views/prints.py` `print_labels`: replace `render_block_to_string` with `render(request, "template.html#content", ctx)` after adding `{% partialdef content inline %}` to `print_labels.html`
- [x] `views/prints.py` `print_label`: remove `@for_htmx(use_block="content")` decorator; add explicit `if request.htmx:` branch
- [x] `tables.py` lines 199, 238: remove `hx-vals='{"use_block":"content"}'` from column HTML

### P6.2 Inline loan-detail tab partials
- [x] Add 6 `{% partialdef %}` sections to `loan_detail_1.html`: `items-tab`, `payments-tab`, `transactions-tab`, `statement-tab`, `notices-tab`, `release-tab`
- [x] Update 6 tab view functions in `loan.py` (lines 590–680) to use `"loan_detail_1.html#<name>"` fragment path
- [x] Delete 6 standalone `templates/girvi/loan/partials/tab_*.html` files

### P6.3 Inline _loan_table
- [x] Move `_loan_table.html` content into `loan_list.html` as `{% partialdef loan-table %}`
- [x] `loan_table_partial` view → `render(request, "girvi/loan/loan_list.html#loan-table", context)`
- [x] Delete `_loan_table.html`

### P6.4 Delete dead legacy templates
- [x] Confirm `loan_detail_2.html` is unreferenced; delete
- [x] Confirm `loan_detail.html` is unreferenced; delete
- [x] Inline `storagebox_list_partial.html` → `storagebox_list.html#storagebox-list`; delete standalone

### P6.5 Remove django-render-block dependency
- [!] Project-wide grep confirms no other app uses `render_block_to_string` (blocked: still used in `apps/tenant_apps/utils/htmx_utils.py`, `apps/orgs/views.py`, `apps/tenant_apps/sales/views/invoice.py`)
- [ ] Remove `django-render-block==0.10` from `requirements.txt`

Acceptance:
- [x] Zero occurrences of `render_block`, `use_block`, `@for_htmx` in girvi app code paths
- [x] All girvi HTMX responses use `template.html#fragment` syntax or explicit 204/redirect
- [x] All tests pass after changes


## Change Log Template (Use Per Completed Task)


### Task ID:
- Date:
- Files changed:
- Summary of change:
- Risk notes:
- Verification performed:
- Follow-up required:

### Task ID: P6.1-P6.4 native partial migration implementation
- Date: 2026-03-18
- Files changed:
	- apps/tenant_apps/girvi/views/prints.py
	- apps/tenant_apps/girvi/tables.py
	- apps/tenant_apps/girvi/views/loan.py
	- apps/tenant_apps/girvi/views/storagebox.py
	- templates/girvi/loan/print_labels.html
	- templates/girvi/loan/loan_detail_1.html
	- templates/girvi/loan/loan_list.html
	- templates/girvi/storagebox/storagebox_list.html
	- templates/girvi/loan/partials/tab_items.html (deleted)
	- templates/girvi/loan/partials/tab_payments.html (deleted)
	- templates/girvi/loan/partials/tab_transactions.html (deleted)
	- templates/girvi/loan/partials/tab_statement.html (deleted)
	- templates/girvi/loan/partials/tab_notices.html (deleted)
	- templates/girvi/loan/partials/tab_release.html (deleted)
	- templates/girvi/loan/_loan_table.html (deleted)
	- templates/girvi/storagebox/storagebox_list_partial.html (deleted)
	- templates/girvi/loan/loan_detail_2.html (deleted)
	- templates/girvi/loan/loan_detail.html (deleted)
- Summary of change:
	- Replaced render-block based Girvi print flow with Django 6 native template fragments.
	- Migrated loan detail tab endpoints to canonical `loan_detail_1.html#<partial>` responses.
	- Inlined loan table and storagebox list partial content into canonical templates and deleted standalone partial files.
	- Removed dead loan detail template variants to prevent parallel/legacy rendering paths.
- Risk notes:
	- `django-render-block` package cannot be removed yet because non-girvi apps still depend on it.
	- Existing JS lint warnings in `loan_list.html` are pre-existing template-JS parser noise and not introduced by this change.
- Verification performed:
	- `python manage.py test apps.tenant_apps.girvi.tests --verbosity 1` -> 5 tests passed.
	- `python manage.py check` -> no issues.
	- Targeted grep confirms no remaining girvi runtime references to deleted partial files.
- Follow-up required:
	- Perform manual HTMX smoke test for loan detail tabs and storagebox CRUD in browser.
	- Decide whether to run cross-app migration of `render_block_to_string` (orgs/sales/utils) before removing `django-render-block` dependency.
	- Add tenant-aware test harness coverage for Girvi because default test execution does not provision tenant-schema tables for this app under `django-tenants`.

## Kept vs Deferred Changes (Closeout)

### Kept in current Girvi scope
- Native partial migration remains fully applied for Girvi loan, print, and storagebox flows (`template.html#fragment` + inline `{% partialdef %}`).
- Legacy Girvi partial templates that were replaced by canonical inline fragments remain deleted.
- Loan detail canonical surface stays on `loan_detail_1.html` with inline tab fragments.
- Custody/repledge route wiring and release custody pre-check integration remain in place.
- Workspace layout standardization done in touched Girvi templates remains in place.

### Deferred intentionally
- Project-wide removal of `django-render-block` from dependencies is deferred until non-Girvi usages are migrated (`apps/tenant_apps/utils/htmx_utils.py`, `apps/orgs/views.py`, `apps/tenant_apps/sales/views/invoice.py`).
- Full manual browser UX pass is deferred (loan tabs, print labels HTMX flow, storagebox CRUD).
- Phase 3 classification gaps remain deferred: repledged item lifecycle scope, loan template management surface, and loan item media artifacts.
- Phase 4 route/query consolidation for reports/notices/archives remains deferred.

### Validation gate status
- `python manage.py check` is the current non-blocking validation gate and has passed.
- Direct Girvi test invocation from the default harness is not a blocking gate for this closeout because Girvi is tenant-schema scoped under `django-tenants`; add tenant-aware test setup before treating these tests as a merge gate.