---
status: implemented-local
owner: loans
updated: 2026-10-03
tags: [khata, performance, read-models, custody, verification]
related: [khata-collateral-usability.md, ../adr/2026-10-01-khata-summaries-and-documents.md]
---


The later [document-navigation checkpoint](khata-document-navigation.md) records the current
local runtime; earlier checkpoint identities/counts below remain dated evidence.
# Khata measured read performance

The owner authorized phase three after searchable servicing. No production change.
The final frozen image at this checkpoint was verified in the fictional localhost
pilot; the later [action-guidance checkpoint](khata-action-guidance.md) records
the guidance runtime identity. Actions now intentionally reads a compact canonical
schedule for due/finalization guidance; History/Collateral/Documents remain source-only.
Existing database/media and prior web are preserved; production is unchanged.

## Reproducible measurement

[The benchmark script](../../scripts/benchmark_khata_reads.py) refuses ordinary
settings/databases: use `django_project.settings.test` and a base DB_NAME beginning
`khata_perf_reads_`. Django creates/reuses a separate `test_` database, constructs
fictional evidence only through supported commands and flushes its fixture after
measurement. It never seeds/imports the pilot or real accounts. Owner setup is
separate from reads: each read assumes the existing non-superuser/non-bypass
restricted role under matching Workspace context, with SELECT grants confined to
the dedicated benchmark database. Four separate connections/readers are measured.

Fixture steps contain 25, 250 and 1,000 received records (41, 288 and 1,113 operations),
one active account plus 40 drafts, photos, receipt/exchange compensation, grouped reservation/handovers
and twelve months of interest. Three warm sequential samples yield median direct
Django-view latency; a separate traced/query-captured sample reports peak Python
allocation and SQL count. Response sizes include HTML/JSON, not photograph bytes.
Network, middleware, browser rendering, PostgreSQL/server RSS and write contention
are excluded. These diagnostics are not a hosted latency SLA or production load test.

Final frozen-image comparison at 1,000 records (before / after):

| Read | Median ms | Peak Python MiB | SQL queries |
| --- | --- | --- | --- |
| Overview | 121.87 / 56.91 | 7.169 / 1.488 | 41 / 39 |
| Actions | 120.02 / 24.56 | 7.171 / 0.234 | 41 / 31 |
| History | 147.97 / 38.22 | 7.229 / 0.431 | 42 / 33 |
| Interest | 132.59 / 35.66 | 7.169 / 0.294 | 41 / 36 |
| Custody | 195.38 / 31.96 | 9.142 / 0.426 | 41 / 33 |
| Documents | 166.86 / 84.16 | 7.876 / 1.680 | 42 / 34 |
| Picker | 20.56 / 18.21 | 0.280 / 0.280 | 21 / 21 |
| Photo form | 85.60 / 87.46 | 2.487 / 2.487 | 42 / 42 |
| Register | 130.88 / 52.33 | 7.550 / 0.796 | 38 / 36 |
| Filtered register | 135.08 / 32.36 | 7.554 / 0.304 | 38 / 35 |

Custody HTML falls from 450,182 to 36,356 bytes. Four simultaneous history readers
finish in 506.86 / 146.88 ms wall time. Tiny-account timing fluctuates: 25-item
Overview is 34.76 / 38.50 ms despite lower allocation. The picker stays bounded;
native photo dropdown rendering remains proportional to held records, so this
change does not claim every workflow is faster.

The final quiet run follows completed regressions. An earlier final-image run
shared the database server with the full regression suite and produced noisier
latencies; its raw evidence remains retained, but it is not used for the table.
The isolated fixture counts and canonical balances agree at all three sizes in
both final runs and the preceding frozen image. Private raw reports and comparison
are retained under `.tmp/khata-performance-20261002/` (`before-final.json`,
`after-final.json`, `after-quiet.json`, `comparison.json`).

## Small coherent changes

- Resolve the selected detail panel before loading balance graphs, source document
  choices, current prices, history or photographs. Document POST failures still
  open Documents; permissions and authoritative issue services remain unchanged.
- Balance-only summaries prefetch complete financial-position sources and exact
  interest evidence. Custody counts are live source queries. Full-source selector
  mode remains available for provenance/comparison; no money projection is stored.
- Register text/state/borrower/series/licence filters narrow Workspace accounts in
  SQL before financial replay. Due/overdue/return attention and totals still cover
  every matched row before pagination; invalid filters do not replay all accounts.
- Custody pages render 25 records and their latest private photo IDs. UUID query
  selection, private scan redirects and history item links target an exact record.
  A small bounded script resolves legacy fragment-only bookmarks outside a page;
  native QR links work without JavaScript. Saved PDFs/printed UUID routes are unchanged.

## Verification and limits

Six new checks compare complete/compact money, terms, schedules, custody counts and
current cover across revised limits/rates, corrected receipts/exchanges, settled
pending/closed accounts and draft/cancelled states. They also check panel independence
from balance replay, bounded custody pages, exact photo/QR/history identities,
foreign-account UUID refusal, context requirements and filtered totals before paging.
They pass in 5.135 seconds; 45 existing cases pass after updating one obsolete QR
redirect assertion. The final frozen image passes **412 Linux regressions in
200.291 seconds**. All 1,405 application/settings files match the archive and actual
image. Schema/no-drift/dependency/restricted-runtime/static/owner-refusal checks pass.

Chromium verifies disjoint custody pages, exact item/photo/source/QR links,
legacy fragment resolution, foreign-account refusal, viewer access and mobile /
no-JavaScript use, plus prior tab/register/searchable-servicing/exception checks.
Desktop/mobile screenshots are inspected; no page JavaScript errors occur. QA
serves the exact configured Bootstrap 5.3.8 bytes with matching SRI because the
sandbox blocks the CDN; application asset configuration is unchanged.

Local candidate: `khata-local-20261002-de09e77ef1d9`, image
`sha256:f8a4023a4b0020b867798afeb457e29e7d6376badee38d2387744f00e26b1ae7`.
Source digest: `de09e77ef1d936fbae2fe3bbeaeee5d0b5d4a1e7bb23126d71fb56b0a7f59eed`;
archive: `6525f136003d1e047127baabbec32f370ab8cecc481efd8c0c32be35ee6c4c15`.
This is an uncommitted local snapshot, not a released or remote-CI identity.
Pre-update database/media backups and checksums are retained, together with stopped
web `khata-img-20261002-web-pre-performance`. Later changes are documentation only.

The benchmark helper is excluded by the web-image allowlist and mounted read-only
from the frozen archive for final-image measurement. Application modules use only
the actual built image; this is not a source-bound substitute for image verification.

No migration, index, new operation, accounting rewrite or persistent cache is added.
LTV suggestions still iterate eligible weights using the existing per-item rounding.
Interest retains complete financially activated history/periods. Document choices,
photo archives, saved-issue lists and native dropdowns still scale; more active
accounts/financial revisions/longer lifetimes and write contention need separate
measurement. Document/search navigation is queued in Future Work. Representative
hosted/hardware/operator acceptance remains open.
