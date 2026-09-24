---
status: review
owner: project
updated: 2026-09-24
tags: [readiness, preferences, navigation, ui]
---

# Preferences and operator UI readiness review

The owner raised dependency, navigation, discoverability and screen-density
concerns before cutover. This is an initial repository inspection, not a completed
browser usability/accessibility audit or authorization to remove stored data.
No application behavior or deployment changed during this review.

The owner subsequently authorized implementation. The first bounded cleanup is
deployed: read-only legacy settings guidance, visible records/report navigation,
and grouped loan-detail disclosures. See [Status](../STATUS.md) for verification
and [the feature map](../flows/workspace-feature-map.md). The subsequent increment
completed dependency retirement with a data-preserving migration, verified on fresh
and populated databases. The findings below describe the pre-cleanup state.

## Dynamic preferences

`django-dynamic-preferences` remains installed in `settings/base.py`, registered
through configuration/orgs app startup, and exposed through shared URLs and
preference forms. Both `configuration.WorkspacePreferenceModel` and
`orgs.CompanyPreferenceModel` remain, along with user/global preferences and a
central service/audit model. Therefore uninstalling the package alone would break
imports and model/form initialization.

Repository searches found no current business consumer of `PreferenceService`
outside the preferences implementation, tests and the `CompanyPreferences`
compatibility wrapper, and no caller of that wrapper outside its definition.
This is strong evidence of unused business configuration, not proof that every
possible external/administrative integration is unused. Inventory persisted rows,
all routes and migration dependencies before removal.

The central registry still declares accounting ledgers, voucher numbering, DEA
integration, inventory and legacy loan defaults. The visible configuration page
advertises central defaults and links to “Legacy Girvi Preferences”. The current
loan workflow instead has dedicated policy/product/licence/document setup.
Theme switching also uses browser localStorage (`static/js/color-modes.js`).
Registered preferences and passing storage tests do not establish that a setting
affects the current application.

Recommended direction: retire unused preference surfaces and registrations;
preserve/export existing values privately and migrate any proven surviving use
before removing models/dependency. Keep financial policy under its existing
versioned domain services. Do not connect obsolete preferences to current loan
calculations just to justify retaining the package. The RLS transition alone is
not evidence that a preferences library is unnecessary or unsafe.

## Navigation and screen organisation

The current sidebar already has Work and Reference & communication groups,
permission filtering and Settings. Bootstrap 5.3.8 CSS/bundle is loaded, and
cards, grids, buttons, alerts and accordions are used. The issue is consistency,
placement and hierarchy rather than absence of the framework.

Concrete findings:

- Historical loan evidence is nested under Settings in the sidebar, despite
  being a routine read workflow. The parent Settings visibility condition does
  not include data.view alone, although the archive child does. Validate actual
  role combinations before changing the navigation permission boundary.
- Business setup, Setup checklist, Loan setup, Preferences and App configuration
  overlap in terminology and perceived responsibility.
- Loan details put balances, origination review, actions, documents, collateral,
  accruals, notices, auction recovery, renewal lineage, audit and events on one page.
  The recent print shortcut addresses one symptom, not the overall hierarchy.
- Reports & reconciliation is a secondary action on the loan list; important
  workflows need a deliberate and consistent home rather than incidental links.

Recommended next increment: map supported features and daily journeys to named
navigation locations; remove misleading settings; review a simplified loan-detail
and navigation prototype before extending the pattern to other screens. Keep
frequent actions visible, group secondary actions, and put detailed history and
exceptional operations behind clearly labelled sections. Use existing Bootstrap
components with keyboard/mobile verification, not a new frontend framework.

## Readiness interpretation

Database/migration verification is evidence of technical progress, not complete
operator readiness. Treat misleading financial settings and inability to discover
essential daily workflows as pre-cutover issues. Cosmetic spacing/icons can follow
once the workflow is usable. Final credentials, recovery and frozen-source
reconciliation remain separate outstanding operational requirements.

Suggested acceptance journeys: find customer, create/review/approve/disburse loan,
print ticket, collect interest/partial principal, release collateral, find historical
records and reports, and administer real loan/template settings. Validate with
ordinary permitted staff roles as well as the owner; preserve existing permission
and financial-service enforcement.

## Staff workflow review outcome (September 24)

Delivered on rehearsal: top-of-dashboard borrower search/work queues, visible
payment receipt links with reversal status, canonical permission-based customer
control visibility, and unambiguous Release batches navigation highlighting.
55 targeted tests and 36 hosted reader/editor/collector page checks passed. Hosted
check identities and grants were transactionally rolled back; no financial actions
were posted. Browser checks cover search-to-loan, payment form, release lookup,
report discovery, dashboard desktop/390px and authorized customer editing.

The report page was the next concrete gap: JCL produced 7,248 table rows, long lists
of borrower statement links and no report-section navigation. A complete fix needs
bounded, selected report queries/pages, rather than simply folding thousands of
rows into collapsed panels. Preserve permission-filtered exports, full export data,
as-of date filters, source-document links and visible integrity failures. Test
pagination across current production-scale data. Do not count this report as
accepted merely because a GET succeeds.

Actual staff acceptance, payment receipt/release memo physical handling and wider
Hindi/device coverage remain separate from this technical review. The receipt
section was tested using repayment and reversal fixtures; no existing hosted
repayment event was available for a live receipt check.

## Reports outcome (September 24)

The report gap above is resolved on rehearsal by
`rokkad:rehearsal-report-pages-v3-20260924`. Eleven selectable reports replace the
all-in-one page. Lists paginate 50 source records before related evidence loads;
statement search uses borrower name/code/phone. Dates and source links survive
navigation. Balance/day/license sections retain their date semantics, histories
remain all recorded activity, and custody remains current stock; the UI labels
these scopes. Full summary and exports deliberately still read the whole portfolio.

Integrity pages inspect 50 loans, potentially producing multiple findings per loan,
and never describe an empty page as global success. The checker now accepts valid
migration-opening origins; JCL's 2,404 false missing-disbursal warnings disappear,
while balance derivation errors and unrelated findings remain enforced.

Twenty distinct targeted tests passed. Hosted checks covered all eleven sections,
pagination boundaries, full-summary equivalence and identical hashes for all seven
CSV datasets; JSK and Lakshmi default reports also passed. Browser checks covered
page navigation, borrower search, preserved dates and desktop/390px layout. The
post-deployment summary showed zero integrity findings with unchanged totals.
One hosted default-page comparison improved from 6.148 to 0.289 seconds, with HTML
reduced from 2,203,055 to 53,662 bytes. This is not a load-test guarantee or complete
staff acceptance. Detailed evidence remains on the server; see Status.

## Borrower discovery and analytical reports (September 24)

The owner requested borrower-filtered loans, licence/series active totals,
collateral values/weights and useful charts. The loan directory now has a dedicated
borrower name/code/phone field and a validated exact Party filter; links from the
customer, loan heading, loan-list borrower and statement directory make it reachable.
Inactive borrowers remain searchable because customer status does not cancel debt.
These filters compose with status, licence, series and dates and survive pagination.

Four new selectable reports show active-loan counts, recorded outstanding balances
and overdue counts by licence or series; net/gross weight and recorded approved
appraisal sums by metal/custody; and maturity age bands. Licence/series table labels
open the corresponding active loans. Charts use the same selector results as tables
and CSV/XLSX/PDF exports; top-twelve grouping affects charts only. Tables remain usable
without JavaScript. Missing balances and incomplete collateral evidence are explicit.
Current status/stock and date-scoped balance/appraisal semantics are labelled.

Twenty-three distinct targeted tests passed. All four reports were checked in each
rehearsal Workspace against canonical active balances/current collateral weights;
CSV totals and group drill-down counts matched. Existing seven JCL export hashes
were unchanged. Exact borrower filtering, pagination and cross-Workspace denial
passed. Full active aggregates took about 2.2-3.7 seconds and collateral summaries
about 0.1 seconds in individual hosted probes; these are observations, not load-test
guarantees. Browser checks cover borrower search and exact filtering, licence
drill-down, charts and phone-width layout. Imported missing appraisal/gross-weight
evidence remains visible; the report does not invent current market valuations.
