---
status: active
owner: project
updated: 2026-09-11
tags: [loans, routing, workspace]
---

# Loans Workspace route migration

R07 is complete locally. All 136 canonical routes in `loans/urls.py` are exposed
through `workspace_loans` using the existing `workspace_view` adapter. Middleware
retains membership, lifecycle, billing and RLS enforcement; original decorated
views retain action permissions. No business services or schema changed.

## Current routing contract

- Canonical `/w/<slug>/loans/...` paths resolve directly to Loans views.
- Templates, Python redirects, HTMX headers, checklist and Party-history links
  generate scoped URLs before responses are created.
- Existing mapped-domain `/loans/...` paths and Workspace aliases remain valid.
- Old list/create/detail/setup aliases call Loans views directly. The old
  `workspace_slug_loans_dispatch` URL name remains for stored/external callers
  building paths; supported paths resolve earlier, and the fallback returns 404.
- No dispatcher resolves another URL, alters `resolver_match`, rewrites response
  HTML or changes `Location`. Binary/streaming responses and headers pass through.
- Forms submit to scoped links or their existing current URL; on old mapped-domain
  entry, the domain remains explicit authority. Query strings remain intact.

The sections below preserve the incremental delivery history. Their earlier
"next" steps and dispatcher descriptions are historical, not outstanding work.
R12 module organization is separate from this routing migration.

## Initial validation and remaining work (historical)

The initial route increment passed 47 of 49 document/media/Workspace tests and
30 additional route-intent checks. The two setup-link failures were reproduced
without that routing change and subsequently traced to incomplete test fixtures.
Both fixtures had a series but no available PawnLoan number sequence, so readiness
correctly offered Set up a series before economics or borrower creation.

The economics-link test now provisions numbering; the borrower-link test provisions
numbering and economic/metal-rate policies. The real readiness selector remains
unmocked. A new test verifies numbering is offered first without creating a sequence
on GET. The route fixture freezes today's date within its license validity period.
No application behavior, access checks or database schema changed for this repair.

Continue migration family by family with full-page, HTMX, redirect and multi-Workspace
coverage. R12 module extraction is still pending; this increment does not claim all
Loans routing is simplified. Current validation totals are recorded in Status.

## Browsing family (2026-09-11)

Collateral list, release list and release detail now resolve through workspace_loans
before the fallback dispatcher. Their filters, pagination and HTMX history handling
remain in the original views. Table cells and templates generate Workspace-scoped
links before rendering. Links to scan and batch-release destinations still reverse
the legacy path and pass it to the named Workspace dispatcher; they no longer depend
on rewriting the browser response. Those destination workflows remain unmigrated.
Loan-detail links use the existing named Workspace alias, and photos/memos use the
already migrated direct routes. Legacy mapped-domain browse routes remain available.

Regression coverage checks populated full pages, HTMX fragments/history restoration,
filter/sort parameters, table links, release detail, cross-Workspace visibility,
removed membership, conflicting domain identity and GET-only lists. Unknown release
IDs from another Workspace remain 404. No business calculations or schema changed.

The subsequent release-batch migration is recorded below.

Validation for browsing: all 69 route/intent/collateral-media tests passed, plus
runtime system checks and current documentation links.

## Release-batch family (2026-09-11)

Four batch routes now use direct adapters. Search-widget URLs, selection and
confirmation actions, loan/release/history links and successful completion redirects
carry the middleware-selected Workspace. Existing mapped-domain entry URLs remain
available and emit scoped links. Browsing-page batch links now target these direct
names too. HTMX previews remain fragments; history restoration returns a full page.

The release services, signed quote validation, collector confirmation and atomic
idempotent completion are unchanged. Tests exercise real HTTP preview/completion/
retry and retained service rollback/expiry/tamper/RLS checks, plus CSRF rejection,
release-action denial with data.view retained, two-Workspace search isolation and
legacy mapped-domain entry. No schema migration or external delivery is involved.

Next: migrate collateral scan navigation, then remaining loan forms/actions in
bounded families. The compatibility dispatcher is still required for those routes.

Release-batch validation: all 61 targeted tests, runtime system check, current
documentation links and whitespace checks passed.

## Collateral scan and label family (2026-09-11)

The collateral scan and label-PDF routes now use direct Workspace adapters. Scanning
redirects to the named Workspace loan detail with the existing collateral anchor.
Verification scans preserve the session/item query and target the Workspace-scoped
verification dispatcher. Existing owner verification checks and the Workspace-bound
pending-storage session value remain unchanged.

Newly generated collateral labels encode an absolute Workspace-scoped scan URL;
existing label evidence and printed QR codes are not rewritten. Legacy /loans/ scan
paths still work on their mapped Workspace domain and redirect to the scoped loan.
This does not give an old unscoped QR URL on a global domain authority from a saved
profile preference. Templates now reverse the direct scan/label names.

Storage-location scan/labels were migrated in the subsequent increment below. No loan, custody or financial service was changed.

Collateral scan/label validation: 71 targeted tests passed; system, documentation
link and whitespace checks passed. Physical camera/printer checks remain deferred.

## Storage-location scan and label family (2026-09-11)

Both storage scan and label routes now use direct Workspace adapters. Newly generated
location labels encode scoped scan URLs. Existing paths and printed labels remain
supported on mapped domains. Storage scan redirects explicitly carry the Workspace
for verification, item transfer and register fallback. Existing owner-only guards,
active-location checks and Workspace-bound pending-item session logic are unchanged.
The register and transfer/verification pages remain on the scoped dispatcher.

Checks cover explicit and previously scanned items, foreign-Workspace pending
selection, stale pending selection cleanup, non-Box/Slot fallback, missing item or
verification IDs, combined verification parameters and the scoped QR target. Scanning
does not move collateral; the transfer form/service remains responsible for changes.

Next: migrate the storage register/create and collateral-transfer forms, preserving
owner permissions, POST validation, redirect queries and movement evidence.

Storage validation: 71 tests passed in the combined run; the new verification
fixture was corrected to use a populated vault and passed separately. All 72
targeted checks are covered. System, documentation and whitespace checks pass.

## Storage register and transfer forms (2026-09-11)

The register, location creation and collateral placement/transfer routes now use
named Workspace adapters. Forms, navigation and successful redirects explicitly
retain the Workspace and the loan's collateral anchor. Storage scans target these
named routes. Original owner guards, hierarchy validation and movement services
remain in use; no schema or business-rule change.

HTTP checks cover direct route resolution, rendered form actions, invalid hierarchy
and destination, initial placement, required transfer reason, successful transfer,
pending-selection cleanup, movement counts and Viewer denial. The broader rerun
also restored two accidentally altered assertions from the prior increment:
released and lost-compensated collateral has no current storage location.

Next: physical-verification routes, including their forms and action redirects.

Validation: all 73 targeted route/media/intent tests passed in one combined run;
runtime system, current-document links and whitespace checks pass.

## Physical-verification family (2026-09-11)

Session list/start, detail/observation, completion, discrepancy resolution and alert
creation use named Workspace adapters. Navigation, filter/POST actions, scan handoff
and action redirects retain Workspace identity without response rewriting. Failed
alert retry still uses the scoped compatibility route and now explicitly returns
to the named verification detail. Existing service rules and owner guards remain.

All 74 route/media/intent tests passed in one combined run. Coverage includes start
scope validation, pending-item completion blocking, invalid item selection, immutable
missing observation and compensated-loss resolution, required compensation evidence,
Viewer denial, POST-only completion/alert, CSRF, duplicate-alert prevention, scoped
retry links and scan query parameters. Runtime system, documentation-link and
whitespace checks pass. No schema change or physical acceptance test was needed.

Next: notice register and operational-notice retry routes; remaining Loans families
still require the compatibility dispatcher.

## Notice register and operational retry (2026-09-11)

The customer-notice register and operational-notice retry endpoint now use named
Workspace adapters. Register filters, setup/navigation and loan links explicitly
retain Workspace identity. Operational retry returns to the scoped license detail
or named verification detail after success or handled failure. Existing setup
permission and POST-only guards remain; delivery services and intent are unchanged.

Customer-notice retry links in the register explicitly use the scoped dispatcher;
these and customer-notice creation are the next bounded migration. Operational
alerts and customer notice intent remain separate existing workflows.

Validation: all 86 targeted notice/media/route/intent tests passed in one combined
run, including register filtering/scoped links, license retry success/failure,
verification retry failure, missing record, CSRF, POST-only and Viewer denial.
The new HTTP fixture uses ordinary test static storage; no production manifest is
required. Delivery mocked. Runtime system, documentation and whitespace checks pass.

## Customer-notice actions (2026-09-11)

Creation and retry now use named Workspace adapters. Loan/report/register links
carry the Workspace, creation supplies an explicit action URL to the shared action
form, and success/handled-failure redirects use the scoped loan detail. Shared
form back/cancel links also use scoped loan detail. Other action forms retain their
existing submission target. Original data.edit guards, confirmation, notice
idempotency and delivery services remain unchanged.

All 87 notice/media/route/intent tests passed. New HTTP checks cover requested kind,
confirmation validation, duplicate creation, retry success and handled failure,
POST-only retry, CSRF and Viewer denial. Creation was scheduled for later; retry
delivery mocked. Runtime system, documentation-link and whitespace checks pass.

Next: license setup routes. Other remaining families still use the dispatcher.

## License setup family (2026-09-11)

Ten license routes now use named Workspace adapters: register, create, detail,
amend, renew, deactivate, activate, expiry alert, register PDF and private revision
download. Forms and successful redirects carry the Workspace. Operational alert
retry returns to named license detail. License pages link explicitly to scoped
series/document/operations routes while those families await migration. Checklist
links were already scoped. Existing setup permissions, revision evidence, document
headers, activation and renewal services remain unchanged.

Next: series creation and configuration routes. The dispatcher remains for other
unconverted families; no schema or license-scoped collaboration change.

Validation: all 98 setup/notice/route/intent tests passed in one combined run.
Coverage includes creation and renewal evidence/download, exact document bytes and
headers, register PDF, non-consuming number previews, direct form actions and scoped
navigation, invalid creation, activation/deactivation, mocked expiry alert, CSRF,
POST-only actions and Viewer denial. System, docs and whitespace checks pass.

## Series creation and configuration (2026-09-11)

Both series routes now use named Workspace adapters. License-detail links and
series form actions carry explicit Workspace identity; configuration redirects to
named license detail. Existing setup guards, Workspace-scoped lookups and atomic
series/sequence services remain unchanged. No counter reset or schema change.

The new HTTP check covers direct forms, invalid width without creation, creation
of both sequences, edit initial values, renamed series with independent counters
preserved, CSRF and Viewer denial. Next: economics and loan-workflow settings.

Validation: all 101 setup/series-service/number-allocation/route/intent tests
passed in one combined run. Runtime system, documentation-link and whitespace
checks pass. No external service or production database action was performed.

## Remaining-family completion (2026-09-11)

Completed economics/workflow settings, products, document layouts/print profiles,
operations/risk/communication, reports/exports, draft/lifecycle/financial/release/
renewal/auction actions and funding routes. The direct adapter includes every
canonical pattern, so new routes inherit explicit Workspace handling. Shared form
and navigation links, HTMX destinations, primary loan actions and borrower-history
links no longer rely on response rewriting. Party history eagerly loads Workspace
to avoid adding a query for every generated link.

Broad validation exposed stale test URL expectations and query-chain mocks; these
were updated to the explicit URLs. The service authorization assertion now checks
its own series instead of unrelated rows in the whole test database, while keeping
the no-DML authorization assertion. No service permission or financial rule changed.

A two-Workspace HTTP matrix covers remaining setup/report/document pages and legacy
aliases with dispatcher access prohibited. Route-contract checks cover all 136
patterns; adapter checks preserve HTML, redirect and streaming bytes/headers.

Completion validation: the broad Loans/Party UI/route/legacy/shell run exercised
594 tests (591 passed; three stale compatibility/UI assertions failed). After
correcting those expectations, all 50 focused route/legacy/shell checks passed,
including a new response-preservation check. This covers 595 distinct checks across
runs, not a claim that one 595-test run occurred. The previously documented setup
shell failure was stale UI wording; current labels pass without changing that page.
Runtime system check, 128 documentation links and whitespace checks pass.

R07 is complete and remains uncommitted with the earlier hardening work. Review and
commit the accumulated checkpoint before R12 module organization. FW-001 license
scope, FW-002 provider acceptance and physical-device acceptance remain deferred.

The checkpoint review subsequently passed all 680 combined Loans/Party UI/billing/
onboarding/deployment/route/shell tests in one run. The staged import guard, migration
drift, system check, documentation links and staged whitespace checks pass. Five
archived documents had malformed line endings normalized without content changes.
