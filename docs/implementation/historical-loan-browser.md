---
status: deployed
owner: project
updated: 2026-10-09
tags: [loans, archive, migration, usability]
---

# Readable historical closed-loan browser

**Release update, 9 October:** this browser and subsequent unified browsing/
supported archive admission are deployed. The local validation and pending
rollout statements below retain the original checkpoint history. See the
[current origin review](historical-loan-origin-review-20261009.md) and
[production release](loan-production-release-lo07.md).

The owner reported that the archive looked as if closed-loan data had been lost:
the list exposed source hashes instead of customer/dates, and detail put items,
payments and other source fields inside raw JSON. The read-only change presents
those retained facts through the existing authorized archive routes.

The [UR-05 extension](unified-loan-recording.md) now adds an explicit reviewed
admission action and source-identity lookup to list/detail. Eligible reconciled
histories can become ordinary closed loans with links in both directions. Archive
payload presentation and original evidence/media remain unchanged. The browser's
source-claim interpretation rules below still apply; reading/accepting an archive
does not itself certify financial history or perform admission.

## Scope and evidence rules

The list searches normalized customer name, loan number and source ID, with 25-row
pagination before per-record summary date formatting. It lists borrower and
original/closed dates, links each retained snapshot, and moves the owner-only upload
link under Historical import tools. Closed operational loans have a separate
ordinary Loans link; they are not moved into this archive.

`loans/selectors/archive.py` presents the authorized document's normalized facts
and existing legacy source graph. Legacy scalar fields are promoted only when
source system, table/external identity and parent loan reference match the exact
archive loan. Ambiguous origins are not guessed. Source borrower, series/licence
and release recipient references remain within the retained graph; no Party/user
lookup or identity creation is performed. Other/nested records remain accessible
through the original JSON/export.

Normal collateral and payment tables distinguish unknown, explicitly empty and
zero values. Additional item fields expose metal, source weight, purity, item
amount/rate/interest. Payment breakdowns expose supplied principal/interest fields;
release records expose recorded timestamps, release number and original person
references, with a source-snapshot recipient name only when unambiguous. Loan and
borrower fields are readable without parsing JSON. Source timestamps and values
are preserved; normalized summary dates use DD/MM/YYYY.

The mutable legacy amount is labelled Stored loan amount (old system), separate
from reported original principal/balance. The page calculates no totals or
collections and does not recreate missing historical financial/custody events.
Contradiction findings remain visible. Original document, findings, private photos,
hashes, export and acceptance rules are unchanged. No migration or architecture
change is needed; the accepted historical-archive ADR still governs this boundary.

## Validation and release boundary

Focused presenter/HTTP regression coverage checks source binding, missing/empty/
zero distinctions, date formatting, escaped source text, payment splits, retained
document/export equality, customer search/pagination, view-only access and foreign
Workspace refusal. Existing archive acceptance/export/RLS tests run alongside it.
The final Linux run passes all **23 tests in 9.749 seconds** in a disposable
fictional database. Chromium verifies the captured Django HTTP responses at
1440/390 px and without JavaScript: readable sections, native disclosures,
pagination rows, secondary upload/export controls and no document-width overflow
or page JavaScript errors. Desktop-list/mobile-detail screenshots are inspected.
This verifies layout on captured responses; HTTP workflow/access assertions are
the separate Django tests, not a live production browser check.

This is a local source change. Production rollout and inspection of real JCL
records through the deployed page remain separate; no real borrower records are
copied into this checkout and no production data reimport is required.
