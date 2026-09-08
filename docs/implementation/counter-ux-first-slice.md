---
status: active
owner: project
updated: 2026-09-08
tags: [ux, loans, navigation]
related: [../plans/project-wide-ux-revamp.md, ../STATUS.md, ../../README.md]
---

# Counter UX: shared shell and loan workflow

The user accepted the sample counter design and requested more collateral detail
in its loan summary. The live implementation keeps ordinary Django templates,
Bootstrap, existing routes, and all existing workflow services.

## Delivered presentation

- Workspace pages use a full-width, light shell with teal actions, a persistent
  Workspace identity, and the supported app navigation before management links.
- Counter / New loan and PawnLoan setup remain explicit Workspace-scoped links.
  Narrow layouts use an in-flow navigation control opening the existing offcanvas,
  so floating navigation does not overlap loan actions.
- Draft entry has section shortcuts and a sticky desktop loan summary. It shows
  borrower, series, product, tenure, entered allocation total, and each item's
  description, metal, gross/net weight, purity, allocation, and photo status.
- Loan detail, financial actions (including disbursal/repayment/full release),
  and transition forms share a persisted summary of original loan and collateral
  facts. Existing settlement quotes and handoff confirmation remain authoritative.

## State and financial boundaries

The draft summary is a display of form inputs, not a financial projection. It
uses text nodes for user-entered descriptions and labels. Removed items are
excluded; unset/invalid allocations do not display a misleading aggregate.
Interest, LTV, deductions, and net cash are supplied by the existing server
economic preview. Editing inputs hides the old preview and prompts a new one.
The persisted summary labels its amount **Original principal**, not balance due.
Form binding, CSRF, RLS, permissions, lifecycle commands, camera capture,
official document issuance, and exact-byte reprints use the existing paths.

## Scope after this slice

The second slice extends Party list/create/edit/detail and KYC navigation, Rates
quotes/source screens, and Notify batches/settings/integration screens. Shared
record grids, headings, tables, and live entry summaries reuse ordinary templates.
The Party photo editor is expandable; closing it stops its existing camera.
Notify configuration is secondary to delivery work, with permissions unchanged.
The third slice extends management/team/billing/account and setup presentation.
`management-ui.css` aligns the existing management layout with the shared counter
styles. Its mobile Navigation button is in page flow. Shared sidebar partials
provide identical account/settings destinations on desktop and mobile. Billing
uses explicit Workspace URLs; Workspace-list links include `show_all=1`.
Loan setup groups configuration, documents/printing, and operations/custody,
with consistent setup navigation throughout subpages. No command or payment
behavior changes. Browser review also found and fixed the missing import for
`WorkspacePreferenceBuilder` in the canonical Preferences route. Physical phone/camera and printer checks remain
deferred; simulated browser checks are not substitutes for those checks.


## Administration verification

The opt-in `test_administration_screens` browser test visits 13 administration
and three setup destinations at 1440px and 390px, checks mobile account navigation,
page overflow, and JavaScript errors. It creates only isolated fixture records
and submits no invitations or payments. Screenshots: `%TEMP%/rokkad-admin-ux`.
The expanded regression gate passes 608/610 checks; two unchanged legacy
preference tests reference unregistered Loan keys and also fail independently.
Their cleanup is separate from this presentation/navigation slice.
