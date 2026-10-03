---
status: implemented-local
owner: loans
updated: 2026-10-03
tags: [khata, reports, cash, custody, csv, verification]
related: [../adr/2026-10-02-khata-operational-report-semantics.md, ../flows/khata-account-workflow.md, khata-collection-worklist.md]
---


The later [document-navigation checkpoint](khata-document-navigation.md) records the current
local runtime; earlier checkpoint identities/counts below remain dated evidence.
# Khata operational reports

The later [action-guidance checkpoint](khata-action-guidance.md) records the current
local runtime. This report checkpoint retains its dated identity and evidence.

Phase five adds a separate Cash daybook and Custody & pending returns page, linked
from the Khata register and ordinary Operational reports. It reuses recorded
financial/custody sources without migrations, posting or ordinary-loan changes.
The fictional localhost pilot is updated and verified; production is unchanged.

## Report contract

Cash defaults to today's business-date range. Inclusive dates, number/borrower /
reference search, series, licence association and date order select sources.
Cash in separates principal and interest; cash out includes payouts and confirmed
refunds. Net movement is not an account debt or closing cash balance. Later
NOT_RECEIVED evidence gives the original receipt zero cash; REFUNDED preserves
the receipt inflow and shows actual refund on its correction date. Originals,
recording dates, references and correction/source links stay visible. Non-cash
exchange corrections are labelled; approvals/accruals are excluded.

Custody includes every account state. The default is physically held, including
pending returns; held/not reserved, pending, returned and all recorded items are
available. Receipt dates only select the cohort; current custody never claims to
be a historical stock snapshot. Search permanent UUID, Item ID, description,
storage or borrower/number; filter metal, series and licence association. Grouped
metal/status totals distinguish records, pieces and net grams. Exact item,
receipt, active reservation and actual recipient/reference/return links explain
both financial reservation and physical handover.

Both use native GET navigation, 25-row pages and all-matching totals before paging.
CSV requires report.export, retains every matching row across pages, labels
knowledge/current-custody dates and includes permanent source identity/URLs.
Downloads are UTF-8 with BOM; potentially executable staff text is escaped.
More than 10,000 matching rows receives an explicit refusal to narrow filters,
never a partial success. Invalid filters receive errors and no substituted rows.
Read/export access follows the existing Loans Workspace boundary and no-store
headers; viewing/exporting does not mutate balances, sources, files or Rates.

## Implementation

- [Selectors](../../apps/tenant_apps/loans/selectors/khata_reports.py) derive SQL cash annotations and current custody from scoped immutable sources.
- [GET view/forms](../../apps/tenant_apps/loans/web/khata_reports.py) apply permissions, validation and paging.
- [CSV service](../../apps/tenant_apps/loans/services/khata_report_exports.py) materializes a bounded dataset inside the authorized Workspace context.
- [Template](../../templates/loans/khata/reports.html) displays derived values and source links; it calculates no accounting.
- [Boundary tests](../../apps/tenant_apps/loans/tests/test_khata_reports.py) cover cash/correction dates, reductions/settlement, custody/compensation, mixed metals/pieces, pagination, exports, validation and access/isolation/no-write boundaries.

## Verification

Eleven focused Linux cases pass in 9.123 seconds. The first focused run caught an
aggregate alias collision; separate aggregate aliases fix it before candidate
freezing or any pilot switch. The frozen image passes **435 Linux regressions in 221.837 seconds**. The existing
historical-loan browser changes present in this shared source snapshot also pass
23 archive presenter/HTTP/export/acceptance/RLS cases in 4.757 seconds in the same
image. These are selected regression suites, not every repository test.

Actual Chromium verifies register and ordinary-report entry links, cash/custody
tabs, date/filter errors, sorting, custody paging, full filtered CSV across pages,
exact item/event/reservation links, no-store headers, unknown-account empty scope,
viewer viewing with export refusal, desktop/mobile and no-JavaScript navigation /
downloads. All 68 currently physically held fixture items appear in the filtered
CSV regardless of page; the five recorded payout rows retain their exact sources.
Prior tabs, searchable servicing, bounded custody/QR, collection/event and
exception-guidance checks pass. Four report screenshots are inspected; tables
scroll within responsive wrappers without document overflow or page JavaScript
errors. Browser harness fixes await the new page DOM and use the actual total
across accounts, rather than assuming two pages. No application fix follows
freezing. QA uses exact configured Bootstrap 5.3.8 bytes/SRI because sandbox CDN
sockets are restricted; app asset configuration is unchanged.

Local candidate: `khata-local-20261002-2fc1557b6beb`; image
`sha256:0a763226b6c8fae3c7cb3628aec2f0f1f313589d15d5e02d87ed6a7136cc5a8b`. Source digest:
`2fc1557b6beb685a53d5001472789e4c2574678fe71aa94f80d29daab52d8816`; archive digest:
`d44a778f269764faac49454980ed8ac8491ebb82e842f52a40888ba7f5fa8beb`. All 1,418 application/settings files match the frozen
archive and actual image. Schema/no-drift/dependency/restricted-runtime/static /
owner-startup-refusal checks pass. The active web is non-root with read-only root;
fictional database/media persist. Pre-update backups/checksums and stopped prior
web `khata-img-20261002-web-pre-reports` are retained. Private evidence lives under
`.tmp/khata-reports-candidate-20261002/`. Later edits are documentation only.
This is an uncommitted local snapshot, not a remote-CI/production release identity.

## Remaining scope

Historical outstanding/as-of balances, cash opening balances, a general ledger,
additional export formats, saved report snapshots and reminders are separate
work. Further correction kinds need explicit cash/custody semantics. Next in the
accepted sequence at this checkpoint was action prerequisites and draft experience,
now delivered in the linked guidance checkpoint. Series status controls are next. Production,
remote CI, hosted/operator recovery and physical acceptance remain separate gates.
