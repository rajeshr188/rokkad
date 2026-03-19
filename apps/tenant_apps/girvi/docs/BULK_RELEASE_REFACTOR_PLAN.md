# Bulk Release Refactor Plan

Last updated: March 2026  
Branch: dea-kiss

## Goal

Make bulk release predictable, safe, and easy to operate by separating preview and commit responsibilities, centralizing validation, and protecting save operations with transaction boundaries.

## Current Pain Points

- View-level orchestration is too dense and mixes concerns.
- Dynamic formset class creation inside view can drift from global formset behavior.
- Cross-row validation is weak (duplicate loan rows, stale release state).
- Commit path lacks explicit transaction and row lock around multi-row save.
- Side effects in form save were not commit-aware.

## Refactor Phases

### Phase 1: Safety and Structure (implemented)

- [x] Added helper functions in view for:
  - selected id parsing
  - summary computation
  - loan-id extraction from submitted formset payload
- [x] Removed dynamic per-request `modelformset_factory` from `bulk_release`
- [x] Standardized on shared `ReleaseFormSet` import for preview rendering
- [x] Added custom `BaseReleaseFormSet` with cross-row validation:
  - duplicate loan checks in formset
  - stale/already released loan checks
- [x] Updated `ReleaseFormSet` to use custom formset class and `extra=0`
- [x] Added transactional commit in `submit_release_formset`:
  - lock selected loans with `select_for_update`
  - re-check release state before save
  - stamp `created_by` on each release row before save
- [x] Made `ReleaseForm.save()` side effects commit-aware (create payment only after committed save)
- [x] Updated single release create path to still persist through commit-aware save

### Phase 2: UX clarity (implemented)

- [x] Merge selection + preview + confirm into a clearer two-step HTMX flow
- [x] Add explicit row-level status badges (Ready / Blocked / Stale)
- [x] Improve summary card formatting and validation message placement
- [x] Disable submit if formset has row errors
- [x] Preserve selected loan ids through review using hidden form fields instead of editable re-selection
- [x] Allow row removal during review via formset `can_delete`
- [x] Restore per-selection preview row rendering with shared `build_release_formset(extra=...)`
- [x] Fix release/payment compatibility with current `GivenLoan` APIs (`total_due`, `interest_due`, `borrower`)

### Phase 3: Service extraction (implemented)

- [x] Move bulk-release preview and commit logic into a service module
- [x] Keep view thin: parse request, call service, render template
- [x] Add explicit strict/partial commit policy (default strict)

### Phase 4: Testing and hardening (next)

- [ ] Add tests for duplicate/stale selection behavior
- [ ] Add tests for race condition protection in commit
- [ ] Add tests for summary consistency from preview to submit
- [ ] Add tests for payment side effects on release save

## Files Changed in Phase 1

- `apps/tenant_apps/girvi/forms.py`
  - `ReleaseForm.save` changed to commit-aware side effects
  - Added `BaseReleaseFormSet`
  - Updated `ReleaseFormSet` factory to use custom formset and `extra=0`

- `apps/tenant_apps/girvi/views/release.py`
  - Added helper parsing/summary functions
  - Refactored `bulk_release` to use shared release formset infrastructure
  - Refactored `submit_release_formset` with transaction + lock + re-check
  - Updated `release_create` to use commit-aware save path

## Files Changed in Phase 2

- `templates/girvi/release/bulk_release.html`
  - Added explicit Select -> Review -> Confirm step framing
  - Updated Step 1 submit copy and review placeholder

- `templates/girvi/release/release_formset.html`
  - Added review-step status badges and action column
  - Rendered selected loans as hidden fields plus readable loan preview
  - Added row removal controls and improved validation message placement
  - Disabled confirm when row or blocking errors are present

- `templates/girvi/release/release_success.html`
  - Added explicit confirmation-step completion messaging

- `apps/tenant_apps/girvi/forms.py`
  - Added shared `build_release_formset(extra=...)` helper for preview rendering
  - Added `loan_preview` resolution for review rows
  - Enabled `can_delete` on the release formset
  - Updated release amount validation to prefer `total_due` over legacy `due()`

- `apps/tenant_apps/girvi/views/release.py`
  - Added review-state flags for row/blocking error handling
  - Switched preview rendering to `build_release_formset(extra=len(selection))`
  - Ignored deleted rows when determining whether confirm should stay disabled

- `apps/tenant_apps/girvi/models/loan.py`
  - Updated `LoanPayment.save()` to support current `GivenLoan` APIs during bulk release commit

## Open Notes

- `release_update_view` currently uses `form.save()` directly; evaluate whether update should create payment side effects or not.
- After UX refactor, consider converting the preview row into a dedicated lightweight DTO/view-model for clearer rendering.
- Bulk release now works end to end with current `GivenLoan` models, but payment/release compatibility still relies on mixed legacy/refactored APIs in a few shared model paths.
- `BulkReleaseService` now supports explicit `strict` and `partial` commit policies with `strict` as the default.

## Files Changed in Phase 3

- `apps/tenant_apps/girvi/services.py`
  - Added `BulkReleaseService` to own selection parsing, summary building, preview context construction, submit binding, and transactional commit orchestration

- `apps/tenant_apps/girvi/views/release.py`
  - Reduced bulk release views to request parsing, service calls, and template rendering
  - Added explicit `commit_policy` read-through to service commit call (default strict)

- `templates/girvi/release/release_formset.html`
  - Added explicit commit policy hidden input on review submit

- `templates/girvi/release/release_success.html`
  - Added optional skipped-row message for partial commit outcomes
