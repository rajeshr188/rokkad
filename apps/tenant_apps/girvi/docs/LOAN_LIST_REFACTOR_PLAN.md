# Girvi Loan List Refactor Plan

> Last updated: March 2026  
> Branch: `dea-kiss`  
> Status: **Phases 1–6 complete. Phase 7 (formal test suite) pending.**

---

## Goal

Refactor the current GivenLoan-only list into a typed list experience (Given / Taken / All tabs), tighten bulk-action safety with explicit action eligibility by tab/type, and reclaim screen space with a compact quick-filter bar plus collapsible advanced filters.

Reuse existing manager methods and keep current endpoints working via backward-compatible URL/query defaults.

---

## Design Decisions

| Decision | Choice |
|---|---|
| List layout | Three tabs: Given / Taken / All |
| Bulk action menus | Split per tab/type (Given gets full menu, Taken gets delete-only, All is read-only) |
| Filter UX | Compact quick-filter bar + collapsible Advanced Filters drawer |
| Route compatibility | Keep existing route names; behaviour evolves via `loan_kind` query param |
| Merge action scope | Given-only, enforced server-side |
| All tab bulk actions | Disabled (read-only + print only, no destructive actions) |

---

## Phase 1 — Baseline & Route Contract ✅ COMPLETE

**Objective:** Introduce `loan_kind` mode contract without breaking existing URLs.

- [x] Add `loan_kind=given|taken|all` query param with `given` as default (backward-compatible)
- [x] Make `loan_list` and `loan_table_partial` views mode-aware
- [x] Document allowed bulk actions per mode:
  - **Given**: release / merge / notify / print / delete
  - **Taken**: delete only
  - **All**: disabled / read-only
- [x] Keep route names `girvi_loan_list` and `loan_table_partial` unchanged

**Files changed:**
- `apps/tenant_apps/girvi/views/loan.py` — `loan_list`, `loan_table_partial`

---

## Phase 2 — Query & Filter Abstraction ✅ COMPLETE

**Objective:** Split monolithic `LoanFilter` into typed filters sharing a common base.

- [x] Extract `BaseLoanFilter` with shared fields: `query`, `loan_date_range`, `date`, `sunk`, `status`
- [x] `LoanFilter(BaseLoanFilter)` — adds `borrower`, `item_type`; `filter_status` uses `release__isnull`; `Meta.model = GivenLoan`
- [x] `TakenLoanFilter(BaseLoanFilter)` — adds `lender`; `filter_status` uses `status=LoanStatus.RELEASED`; `Meta.model = TakenLoan`; overrides `universal_search` to query `lender__firstname/lastname`
- [x] Remove duplicate `LoanPaymentFilter` definition
- [x] `loan_list` instantiates correct filter class per `loan_kind` mode
- [x] Lazy queryset builders (`get_given_qs()` / `get_taken_qs()`) to avoid cross-model field errors

**Files changed:**
- `apps/tenant_apps/girvi/filters.py`
- `apps/tenant_apps/girvi/views/loan.py`

**Key fix:** `get_taken_qs()` uses `.with_metal_weights().with_itemwise_amounts().with_current_value()` — NOT `for_table_display()`, which references `release__` annotations absent on `TakenLoan`.

---

## Phase 3 — Table Layer for Mixed Model Support ✅ COMPLETE

**Objective:** Replace single `GivenLoan`-bound `LoanTable` with typed tables per tab.

- [x] `LoanTable` (modified) — added `loan_type` badge column (renders `Given`), added `party` column (delegates to `render_borrower`)
- [x] `TakenLoanTable` (new) — mirrors `LoanTable` for `TakenLoan`; `loan_type` badge renders `Taken`; `render_loan_id` routes to `girvi:taken_loan_collateral_detail`; `render_months_since_created` falls back to `record.months_elapsed` if annotation absent
- [x] `UnifiedLoanTable` (new) — dict-based table for All tab; `render_loan_id` routes to correct detail URL per `loan_type`; `render_loan_type` renders appropriate badge
- [x] All three `render_loan_type()` methods return `mark_safe(...)` strings (Django 6 requires this — plain strings are auto-escaped; `format_html()` with no args raises `TypeError`)

**Files changed:**
- `apps/tenant_apps/girvi/tables.py`

**Bug fixed:** `TypeError: args or kwargs must be provided` — Django 6 `format_html()` requires at least one substitution arg. Replaced with `mark_safe('<static-badge-html>')`.

---

## Phase 4 — Bulk Action Hardening ✅ COMPLETE

**Objective:** Make every bulk endpoint safe against bad input and type mismatches.

- [x] `_parse_selected_ids(raw_ids)` helper — deduplicates, rejects non-positive integers, returns `(cleaned_ids, invalid_count)`; defined in both `views/loan.py` and `views/prints.py`
- [x] `merge_loans` — rejects `loan_kind != "given"` with HTTP 400; validates IDs; checks all IDs exist in DB; validates same borrower; blocks merging released loans
- [x] `deleteLoan` — `loan_kind`-aware; blocks All-tab delete; validates IDs; blocks released loan deletion; redirects to `girvi_loan_list?loan_kind=<kind>` after success
- [x] `print_labels` — guards `loan_kind != "given"` → HTTP 400; validates selection IDs; explicit 400 for no selection or stale IDs; removed debug `print()` calls
- [x] `notify_print` — same guards; IntegrityError path now logs exception and returns HTTP 500 (was silently continuing with undefined `notifications`)
- [x] JS front-end: disable action dropdown until selection > 0; show reliable selection count after HTMX swaps; `toggle(source)` iterates only visible checkboxes

**Files changed:**
- `apps/tenant_apps/girvi/views/loan.py`
- `apps/tenant_apps/girvi/views/prints.py`

---

## Phase 5 — Filter Panel UX Refactor ✅ COMPLETE

**Objective:** Move from 3/9 sidebar split to table-first layout with compact quick filters.

- [x] Compact quick-filter row at top: search input, status dropdown, date shortcut — all `hx-get` to `loan_table_partial`
- [x] Full crispy form moved into collapsible Advanced Filters panel (closed by default)
- [x] Hidden `input[name=loan_kind]` field preserves active tab across filter submissions
- [x] Table-first layout (full width); advanced panel optional below

**Files changed:**
- `templates/girvi/loan/loan_list.html`

---

## Phase 6 — Template & Endpoint Integration ✅ COMPLETE

**Objective:** Wire tabs, HTMX partials, and bulk menus together into the final template.

- [x] `{% partialdef loan-content inline %}` — full page with nav-pills tabs (Given / Taken / All), quick-filter form, advanced filter collapse, lazy `#loan-table-container`
- [x] `{% partialdef loan-table %}` — table fragment; bulk action dropdown split by `{% if loan_kind == 'given' %}` / `{% elif loan_kind == 'taken' %}` / `{% else %}`
- [x] Given tab actions: Print Labels, Release, Notify, Merge, Delete
- [x] Taken tab actions: Delete only
- [x] All tab: disabled message shown in place of action menu
- [x] HTMX: `hx-trigger="load"` on `#loan-table-container` for lazy load; tab switch pushes new `loan_kind` param; `htmx:afterSwap` re-syncs selection count
- [x] Stats `<details>` block with loan count and value totals per tab

**Files changed:**
- `templates/girvi/loan/loan_list.html`

---

## Phase 7 — Validation & Rollout 🔲 PENDING

**Objective:** Formal testing across all tabs, bulk actions, and edge cases.

- [x] `python manage.py check` — passes cleanly (0 issues)
- [ ] Given tab: filters, pagination, row detail links, all bulk actions
- [ ] Taken tab: filters, pagination, row detail links, only allowed actions visible and enforced
- [ ] All tab: mixed dataset render, restricted actions behaviour
- [ ] HTMX lifecycle: selection count persists after table reload, tab switch, and filter change
- [ ] Mobile UX: quick filters visible, advanced panel collapsed by default, table is primary content
- [ ] Negative tests: submit bulk action with invalid/mixed IDs directly — server rejects with clear message
- [ ] Regression: dashboard and loan detail navigation from list rows unchanged

---

## Bugs Encountered & Fixed

### Bug 1 — `FieldError: Cannot resolve keyword 'release'`

| | |
|---|---|
| **URL** | `GET /girvi/girvi/loan/` |
| **Cause** | Both `loan_list` and `loan_table_partial` eagerly called `for_table_display()` on TakenLoan at function entry (before `loan_kind` was checked). `for_table_display()` applies `release__…` annotations via shared duration chain — not available on `TakenLoan`. |
| **Fix** | Moved queryset construction into lazy closures `get_given_qs()` and `get_taken_qs()`. `get_taken_qs()` uses `.with_metal_weights().with_itemwise_amounts().with_current_value()` only. Only the queryset(s) needed for the active `loan_kind` are built. |

### Bug 2 — `TypeError: args or kwargs must be provided`

| | |
|---|---|
| **URL** | `GET /girvi/girvi/loan/table/?loan_kind=given&query=&status=All` |
| **Cause** | Django 6 enforces that `format_html()` must have at least one substitution argument. Three `render_loan_type()` badge methods called `format_html('<static-string>')` with no `{}` placeholders. |
| **Fix** | Replaced with `mark_safe('<static-badge-html>')`. |

### Bug 3 — Badge HTML escaped in table cell

| | |
|---|---|
| **Symptom** | `<span class="badge …">Given</span>` rendered as literal text |
| **Cause** | Plain Python strings returned from `render_*` column methods are auto-escaped by Django's template engine. |
| **Fix** | Wrapped all three badge return values in `mark_safe()`. |

---

## Key Files

| File | Role |
|---|---|
| `apps/tenant_apps/girvi/views/loan.py` | `loan_list`, `loan_table_partial`, `merge_loans`, `deleteLoan`, `_parse_selected_ids` |
| `apps/tenant_apps/girvi/views/prints.py` | `print_labels`, `notify_print`, `_parse_selected_ids` |
| `apps/tenant_apps/girvi/filters.py` | `BaseLoanFilter`, `LoanFilter`, `TakenLoanFilter` |
| `apps/tenant_apps/girvi/tables.py` | `LoanTable`, `TakenLoanTable`, `UnifiedLoanTable` |
| `templates/girvi/loan/loan_list.html` | Tabs, quick filters, advanced drawer, split bulk menus, HTMX wiring |

---

## Deferred / Out-of-Scope

| Item | Decision |
|---|---|
| All-tab richer filtering (date/series/party) | Explicitly skipped; implement only if re-requested |
| HTMX inline error banners for 400 bulk responses | Not yet started; suggested but not approved |
| Taken detail template polish (Given-centric view) | Evaluate separately after Phase 7 testing |
| Pre-existing lint in `loan.py` | Unused imports (`PermissionDenied`, `TableExport`, etc.); safe to clean up independently |
