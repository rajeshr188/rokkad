---
status: active
owner: loans
updated: 2026-09-09
tags: [loans, collateral, releases, navigation]
---

# Finding collateral and releases

Within a Workspace, choose **Collateral** or **Releases** from the Work sidebar.
Both pages use 25 records per page. Search and filters are combined; column headings
sort the results. Search, sorting and pagination retain query parameters in the URL,
so a filtered page can be bookmarked. Clear returns to the unfiltered list. HTMX
updates the list without replacing the navigation; ordinary GETs work without it.

## Collateral

Search by item description, the printed CI identifier (or full UUID), loan number,
borrower name or Party code. Filter by metal, custody, loan status or storage location.
A storage filter includes its child locations. Draft and cancelled loans remain
searchable: read the loan status alongside custody when assessing physical holdings.

Open an item to reach its existing loan section, including photos, weights, purity,
appraisal and storage information. The loan page also links to its release records.

## Releases

Search by release number, loan number, borrower name or Party code. Filter by full
or partial release, inclusive effective-date bounds, and recorded/reversed status.
Invalid filters display errors rather than silently returning an unfiltered result.

Open a release to see its settlement breakdown, original recorder/time, item return
timestamps, current custody, and release memo PDF. A reversal banner preserves the
original record and explains that the loan holds current balances and custody.
Perform new releases and other lifecycle actions from the loan, using its existing
permissions and validation. These browse pages never alter loan or release evidence.

All lists, filter choices and details belong to the current Workspace and require
Loans viewing permission. Direct links do not bypass membership or RLS.
