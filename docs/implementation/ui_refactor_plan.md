---
status: active
owner: project
updated: 2026-06-18
tags: [implementation, ui, refactor, plan]
related: [../product/page_hierarchy.md, ../product/userflows.md, ../product/workflows.md, ../ui/screen_designs.md, ../ui/htmx_interactions.md, ../architecture/navigation_map.md]
---

# UI Refactor Plan

This plan turns the product/navigation/userflow design into implementation phases. It is documentation-only until a phase is approved for code changes.

## Principles

- Accounting remains the backbone.
- Users work with source documents, not raw journal entries.
- Posted accounting effects are immutable; corrections happen through reversals.
- Each document detail page should show business, inventory/commodity, accounting, and audit impact.
- Keep server-rendered Django templates with Bootstrap 5, HTMX, crispy forms, and django-tables2.
- Use the current template sidebar as source of truth until a full dynamic navigation migration is approved.

## Phase 1: Navigation And Labels

Status: proposed.

Tasks:

- Rename user-facing sidebar labels:
  - Contacts -> Parties after Party UI exists.
  - Product -> Inventory.
  - Girvi -> Loans or Girvi Loans.
  - DEA -> Accounting.
- Change Accounting sidebar target from journal entries list to Accounting dashboard.
- Add Reports and Settings sections.
- Keep old URLs as compatibility aliases.

Acceptance:

- Sidebar matches user jobs.
- Permission gates still use canonical codenames.
- Navigation validation tests cover URL names and permission codenames.

## Phase 2: Workspace Dashboard Redesign

Status: proposed.

Tasks:

- Redesign `workspace_dashboard`.
- Add action-first buttons.
- Add setup checklist.
- Route setup blockers through app facades/selectors.
- Add recent activity feed.

Acceptance:

- New user knows what to set up next.
- Daily user can start sale, purchase, loan, repayment, payment, and stock adjustment quickly.
- Missing rates/accounting setup no longer causes confusing downstream errors.

## Phase 3: Party UI

Status: proposed.

Prerequisite:

- Party rollout Phases 0-3 are complete.

Tasks:

- Add Party list/detail/create/edit.
- Add role/contact/address/document partials.
- Add legacy Customer link/bridge visibility.
- Add duplicate/merge placeholders.

Acceptance:

- User can create one entity with multiple roles.
- Existing Customer records are visible through Party.
- Contact UI can be treated as compatibility/legacy.

## Phase 4: Standard Document Detail Pattern

Status: proposed.

Targets:

- Loan detail.
- Sale detail.
- Purchase detail.
- Voucher detail.
- Stock detail.

Tasks:

- Add consistent tabs: Overview, Lines/Items, Payments, Inventory/Commodity, Accounting, Attachments, Timeline.
- Use lazy HTMX tab loading.
- Standardize action bar.

Acceptance:

- User can trace every operational document to accounting and stock impact.
- Accountants can drill from ledger/journal back to source documents.

## Phase 5: Accounting UX Cleanup

Status: proposed.

Tasks:

- Consolidate DEA dashboards.
- Make Accounting dashboard the main accounting entrypoint.
- Emphasize vouchers, posting exceptions, periods, and reports.
- Add visible source-document links in voucher/journal screens.

Acceptance:

- Normal users see business actions.
- Accountants see voucher/journal/ledger traceability.
- Posting errors are actionable.

## Phase 6: Sales And Purchase UX Cleanup

Status: proposed.

Tasks:

- Align Sale and Purchase forms/details.
- Move item lines to standard HTMX line editor.
- Add Accounting Impact and Inventory Impact tabs.
- Add allocation modals for receipts/payments.

Acceptance:

- Sale and purchase feel like mirrored workflows.
- Inventory and accounting side effects are visible.

## Phase 7: Loan UX Cleanup

Status: proposed.

Tasks:

- Standardize lifecycle display language.
- Move transition actions into a consistent action bar.
- Improve repayment/release modals.
- Add setup blocker panel for rates, license, series, and party/account mapping.

Acceptance:

- Loan status is understandable.
- Disbursal/repayment/release failures are shown as setup or posting issues, not generic messages.

## Phase 8: Reports Hub

Status: proposed.

Tasks:

- Add central Reports hub.
- Link existing DEA, Girvi, Contact, Product, Sales, Purchase reports.
- Add shared period/date filters.
- Add export permission checks.

Acceptance:

- Users do not need to know which app owns a report.
- Reports drill down to source documents.

## Phase 9: Route Cleanup

Status: proposed.

Tasks:

- Remove duplicate route names after templates move to canonical URLs.
- Keep redirects for old paths.
- Fix nested `/girvi/girvi/...` style paths.
- Split duplicate Product `stock/create/` routes.
- Resolve duplicate Sales `sales/` home/list route.

Acceptance:

- URL names are stable and searchable.
- Navigation tests catch broken links.
- Old bookmarked URLs redirect during migration.

## Phase 10: Dynamic Navigation Review

Status: future.

Trigger:

- Only revisit after template sidebar becomes too hard to maintain or tenant-specific navigation is required.

Tasks:

- Follow `docs/adr/sidebar-navigation-source-of-truth.md`.
- Migrate all sidebar items at once into a nav resolver.
- Add reverse/permission/active-state tests.

Acceptance:

- No dual source of truth.
- Runtime nav is generated from one resolver.
