---
status: verified-local
owner: loans
updated: 2026-10-17
tags: [loans, dashboard, counter, usability, performance, acceptance]
related: [everyday-counter-workflow-review-20261016.md, ../plans/everyday-counter-improvements-20261016.md, ../adr/2026-10-16-everyday-counter-summaries.md]
---

# Everyday counter improvements: local acceptance

Subsequently deployed in the [17 October release](counter-release-20261016.md).
This note retains the earlier local observations and bounds; the release record
adds complete-suite fixes, exact-source CI and production acceptance.

The owner approved the [review's recommended order](everyday-counter-workflow-review-20261016.md).
All seven scoped slices are implemented locally on `work/loan-servicing-contract-ld01`
over `f1ebb75a`. This record does not select a commit, push or deployment.

## Delivered behavior

1. Paper admission states a historical checked-through claim only when its retained
   confirmed-complete flag supports it. Optional book assurance remains separate
   from represented-position transaction coverage and current action readiness.
   Obsolete mandatory-book guidance is removed; existing action guards remain.
2. Active detail shows the existing servicing position's collection amount and its
   basis, date and principal/interest/fee components. Recorded balances remain
   separately labelled. The synthetic native example now prominently distinguishes
   INR 1,000 recorded debt from INR 1,080 to collect, including INR 80 eligible
   unposted interest. Legacy recorded-only contracts keep that narrower label;
   unsupported amounts remain unavailable. Payment/release reviews recalculate.
3. Loan work retains validated list, Dashboard or overdue-page return context,
   including filters and page. Successful actions retain that context on their
   ordinary loan/review destination. External, malformed, cross-Workspace and
   unrelated action origins are rejected; exports, nested returns, fragment modes
   and unknown controls are removed. Return context confers no authority.
4. Detail shares prepared financial inputs within the request and removes repeated
   reads, including reversal readiness for viewers who cannot administer reversals.
   Matching loan/date/Workspace guards and narrower legacy fallbacks remain.
5. The directory has collapsed filters, applied-filter badges and status quick
   views that stay synchronized after HTMX search. Optional current amounts and
   authorized payment links apply only to displayed active rows (page size 25).
   They default on for a borrower filter or a search returning at most three active
   rows; broad browsing defaults off. Existing collateral summaries and filtered
   Excel remain. No portfolio-wide financial fold or unpaid-month computation is
   added to list rendering.
6. Shared direct/paper entry has a sticky entered-principal strip and a link to
   review actions, compact explanatory disclosures and an unsaved-edit warning.
   Preview/error redisplays remain protected. Normal submission, back-cache return
   and HTMX lifecycle are covered. No borrower facts are saved in browser storage.
   Existing draft saving, validation, item allocation and financial review remain.
7. Dashboard's existing queue section adds today's ordinary-loan issues/recorded
   payout proceeds and actual-effective-date repayment/release receipts, including
   loans now closed. Current reversals exclude originals; future reversals do not.
   Invalid receipt evidence makes all receipt amount totals unavailable, with its
   failure count visible. Renewal offsets, auction recovery and Khata are excluded
   and disclosed. Figures do not certify physical cash. The overdue queue previews
   five loans and links to the existing complete, permission-checked work page.

These boundaries are recorded in the [decision](../adr/2026-10-16-everyday-counter-summaries.md).
No financial formula, posting contract, schema migration, loan state, monitoring
currentness rule, portable profile or worker scheduling change is introduced.

## Local measurements

Same small fictional HTTP fixtures, one final observation per route:

| Route | Review queries | Final queries | Final server ms |
|---|---:|---:|---:|
| Native detail | 275 | 192 | 290.97 |
| Paper detail | 303 | 203 | 437.81 |
| Borrower-filtered native list | 85 | 103 | 168.87 |
| Borrower-filtered paper list | 87 | 105 | 146.38 |
| Full Dashboard | 81 | 84 | 187.52 |
| Dashboard queues | 48 | 51 | 53.91 |
| Dashboard overview | 42 | 42 | 78.28 |

Detail reads fall by about 30%/33%. Filtered lists now include collection amounts
that the baseline did not calculate; the Dashboard adds the daily block. These
observations are not production latency, load or capacity claims. Direct entry
remains 129 queries; paper entry remains 95. The phone native-list result heading
moves from 1,022px to 788px. Entry's improvement is disclosure, action access and
edit protection; it is not a major reduction in document height.

## Verification and evidence

All database checks use the private synthetic
`test_rokkad_architecture_snapshot_20261016` database and test settings. A dedicated
daily-activity test executes under a restricted NOBYPASSRLS role and verifies
Workspace separation and the context guard. No live customer data is used.

- The broad affected selection executes 161 cases: 160 pass, with one obsolete
  assertion that Dashboard must hide every overdue loan. It is updated to require
  the approved five-loan preview while retaining complete-page access/pagination
  checks. The subsequent 47-case selection passes, including that corrected test,
  final counter/daily semantics and existing payout/evidence browser acceptance.
- The final 22-case selection passes after the compact-filter and unsaved-guard
  refinements: three new layout methods, current directory amounts and the full
  unified-directory suite. These selections overlap; counts are not unique totals.
- Twelve Node cases pass: six unsaved-entry lifecycle cases plus existing
  directory/editor cases. Python syntax/import boundaries, Django system checks
  and `makemigrations --check --dry-run` pass; no model changes are detected.
- The permanent `scripts/check_counter_workflow_layouts.py` captures nine states
  at 1365px and 390px (18 renders), exercises 24 detail-tab selections and six
  actual browser unsaved-edit assertions. No horizontal overflow, duplicate IDs
  or browser script errors are found. Existing payout/evidence checks cover
  another 14 desktop/phone states. Representative list, detail, entry and Dashboard
  screenshots are visually inspected.
- The unconfirmed paper fixture still has no book review, retained admission
  confirmation is false, transaction coverage is `RECORDED_POSITION`, and book
  assurance is `UNCONFIRMED`. Neither the false checked claim nor the obsolete
  mandatory-auction claim is rendered. A separately confirmed admission retains
  its explicitly historical claim.

Reproducible tests live in `test_counter_workflow.py`, `test_daily_counter.py`,
`scripts/test_counter_entry.cjs` and the layout script. Local task logs are under
`.tmp/everyday-counter-20261016/`; captures and JSON measurements are under
`outputs/everyday-counter-20261016/`. These generated artifacts are ignored.

## Remaining bounds

No production acceptance, live camera/provider validation or large-history/load
claim is made. Existing historical sections remain eagerly prepared; pagination
or deferred loading needs a measured follow-up. Record-and-enter-next remains
later work requiring its own duplicate-submission behavior. Worker scheduling,
source-bound durable reuse and pool sizing remain under existing FW-004 gates.
The daily block deliberately has narrower scope than a complete cashbook.
Commit, release coordination and production verification remain separate steps.
