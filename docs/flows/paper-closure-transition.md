---
status: active
owner: project
updated: 2026-09-25
tags: [loans, staff-guide, release]
---

# Staff guide: paper closures and system-first releases

Use **Loans > Record paper closures**, or **Paper closures** in the sidebar, only
after payment and all pledged items have already been handed over according to
the paper book. For payment being collected now, open the loan and choose Full
release. Release multiple loans is for a single combined counter collection.
Never enter the same closure through both routes.

1. Choose the actual closure date (today by default), optional shared book/page,
   and up to 50 loan numbers. One date per submission; no daily submission limit.
2. Review calculated dues for that date. Actual cash defaults to that suggestion;
   check it against the book. Payer and recipient default to borrower. Expand a
   row's details to change identities, reference or authorized interest concession.
   Another recipient needs relationship and authority-to-collect evidence.
3. Select ready rows and confirm once that collection and completed return match
   the paper record. Every selected row saves or none does. Unselected rows remain
   on screen with their inputs; navigating away discards unsubmitted entries.

A quote lasts ten minutes and is rechecked on submission. Changed dates or loan
activity need review again. Discounts require settings-administrator permission
and an explicit interest concession/reason. Cash plus concession must equal due;
principal, capitalized interest and fees cannot be waived, and excess collections
are not silently treated as interest. Ordinary staff can record exact settlements.

Blocked rows explain missing setup/accrual/valuation, custody, financial activity
or chronology. Do not substitute today's date for an earlier closure to bypass
checks. Imported loans cannot be closed on or before the migration opening date.
For native loans, finalize completed interest periods using the ordinary workflow.
The paper path does not change historical rates or calculate from current defaults.

History shows effective date, actual collections, entry time/actor and each receipt.
Individual PDFs are optional; no customer notifications are sent automatically.
Unknown handover time is labelled honestly. Download the CSV for count/cash
reconciliation with the book. Original batch totals remain unchanged after a
reversal, and reversed rows are marked. Authorized corrections reverse individual
releases; they never edit original batch evidence.

The CSV is not a restorable package. Strict loan-history/opening export currently
rejects paper-closure histories because those profile versions cannot represent
date-only handovers and all per-line evidence. Full database backups retain them.

## Retirement for each branch

The owner opens **Move this branch to system-first**, chooses a start date and
records the reason. New closures from that date use Full release in Rokkad;
earlier paper backlog stays open for entry. Once counts, collections and unresolved
rows are reconciled, the owner checks **Retire routine paper entry**. History stays
available. Administrators may enter late discoveries/outage closures with a reason.
The owner may reopen routine entry with a reason by adjusting both retirement and
the system-first date. Changing one branch never changes another branch.
