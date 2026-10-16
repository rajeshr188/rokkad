---
status: reviewed-local
owner: loans
updated: 2026-10-16
tags: [review, dashboard, loan-entry, directory, usability, performance]
related: [loans-architecture-hardening-20261016.md, ../flows/business-dashboard.md, ../flows/unified-loan-recording.md]
---

# Everyday counter workflow review

The owner identifies Dashboard, paper/direct loan entry, Loans list and loan
details as Rokkad's most-used screens and requests a review for improvements.
This is a review of committed local source at `f1ebb75a`, including loan commit
`42564f6d`. The newer policy/coverage changes are locally verified but not deployed.
Findings below must not be presented as a fresh inspection of production.

The owner subsequently selected the recommended order. See the
[local implementation and acceptance](everyday-counter-improvements-20261016.md).
This review preserves its original findings and baseline observations.

## Conclusion and existing strengths

Prioritize factual amounts and evidence wording, continuity between screens,
compact counter work and bounded reads. Keep the shared loan model, entry editor,
financial calculators and ordinary action services. No additional origination
engine, general workflow framework or independent financial dashboard is needed.

Useful foundations already exist: shared paper/direct item entry, standing defaults,
searchable borrowers, explicit review/confirmation, draft saving for direct loans,
collateral previews, filtered Excel export, state-based detail actions, keyboard
operable detail tabs, retained history and independently loaded dashboard sections.
Retain these rather than re-propose them as missing features.

## Findings and proposed delivery order

| ID | Priority | Finding | Smallest useful improvement |
|---|---|---|---|
| EC-01 | First: correctness | A paper loan recorded without optional book confirmation still renders a positive checked-through claim and mandatory-confirmation guidance | Derive wording from actual assurance evidence and the shared position contract; keep unconfirmed assurance separate from usable represented position |
| EC-02 | First: correctness | Native detail calls recorded principal/interest/fees "Current balance / Total due" while eligible unposted interest is elsewhere | Present a clearly labelled current collection amount and breakdown from the existing servicing summary; retain recorded balance and monitoring exposure under their own labels |
| EC-03 | Next: daily continuity | Detail's Loans link discards borrower/search/status/page; Previous/Next follows the series rather than the filtered work list | Carry validated Workspace-local return context and distinguish series navigation from search/queue navigation |
| EC-04 | Next: speed foundation | Small synthetic detail reads use 275/303 SQL queries; hidden sections are still eagerly assembled | Measure repeated reads, reuse request-scoped prepared inputs and defer genuinely heavy secondary sections without weakening action-time checks |
| EC-05 | Next: list usability | Results follow a large filter/help area; rows show original principal but require a detail open for current money and action | Compact filters/help, explicit useful quick views, and bounded current-amount summaries with permission-aware links to existing payment/detail commands |
| EC-06 | Then: entry throughput | Routine entry is long on a phone, summary follows the action area, and there is no general unsaved-change warning | Focus defaults/essential fields, move reference explanations into disclosures, keep a compact summary/action affordance, and warn before discarding edits |
| EC-07 | Then: dashboard usefulness | Dashboard leads with useful search/queues but activity covers issues/renewals, not actual collections; default overdue selection renders no inline queue preview | Add a compact daily outcomes block and a small actionable queue preview using existing canonical evidence and dedicated work pages |

### EC-01: paper assurance wording is factually inconsistent

A synthetic ordinary paper entry is confirmed with optional book confirmation
left off. No LoanTransactionReview exists; the retained admission explicitly has
`confirmed_complete=False`. The shared evidence result correctly reports
`RECORDED_POSITION` and optional book status `UNCONFIRMED`.

Nevertheless, the [Recorded from paper panel](../../templates/loans/pawn/detail.html)
says "paper activity was checked through" a date and says auction recovery requires
complete transaction confirmation. It also describes reminders as available only
after transaction confirmation. Those sentences contradict the accepted
[represented-position treatment](../adr/2026-10-16-represented-position-transaction-coverage.md).
The displayed checked-through statement is a confirmed presentation defect, not
evidence of an incorrect financial balance or a fabricated stored review.

Show a positive checked-through claim only when actual retained assurance supports
it, identifying its date/history limit. Otherwise state that original facts were
recorded and optional book reconciliation is unconfirmed. Keep known unresolved
activity visible. Reuse shared action eligibility for recovery/reminder guidance;
consent, statutory, custody and source/date/amount checks still apply. Add explicit
semantic tests for unconfirmed, confirmed, aged and unresolved cases when fixing
this: layout visibility checks alone do not verify the truth of the copy.

### EC-02: one clear collection amount with explicit bases

The native synthetic fixture has INR 1,000 recorded debt and INR 80 eligible
unposted interest. The shared [loan summary](../../apps/tenant_apps/loans/selectors/loan_summary.py)
returns INR 1,080 under "Collection amount including eligible unposted interest".
The prominent [detail balance panel](../../templates/loans/pawn/detail.html)
instead displays "Current balance" and "Total due" of INR 1,000, with interest
outstanding zero. Four available interest periods are mentioned separately and
economic exposure is in Money & interest. These are distinct legitimate financial
reads; the prominent label does not make that distinction clear enough for staff.

Use the same supported servicing summary as export/collection workflows for an
as-of-date "Amount to collect" with principal, interest and fees. Keep original
principal, finalized recorded debt, contractual amounts due and monitoring
exposure distinct. Collection, scheduled instalment due, maturity payoff and risk
exposure are not interchangeable. Unsupported/legacy profiles retain their actual
basis or an explicit unavailable result. Preview the action's exact quote again
before posting; a page summary never authorizes collection or concession.

Also standardize rupee presentation and plain-language status labels across these
screens; technical contract/status tokens belong in detailed evidence disclosures.

### EC-03: preserve the task across navigation

The list can retain borrower/state/search/page in its URL, and its Excel export
correctly preserves filters. However, the [detail header](../../templates/loans/pawn/_detail_header.html)
links to the unfiltered list. Its Previous/Next is explicitly series navigation.
Dashboard queue links similarly arrive without a return-to-queue instruction.

Carry an explicit validated local return location from list/dashboard through
detail and supported action completion. Restore filters and page, with scroll/focus
where practical. If a result leaves the selected set after a payment/closure,
explain that and return to the remaining work. Never accept an arbitrary return
URL or use navigation state to grant permissions. Keep series traversal available
and clearly labelled when it differs from the current search or queue.

### EC-04: reduce repeated reads before adding richer summaries

The [detail lookup](../../apps/tenant_apps/loans/web/pawn_read_helpers.py) prefetches
collateral/photo/storage, accrual lines, changes, events, releases and approvals.
The [view](../../apps/tenant_apps/loans/web/pawn_reads.py) also prepares live financial,
risk, servicing/correction, appraisal and history data before choosing a client-side
tab. Its event-row builder assesses reversal readiness for every event even when
mutation authority is absent. Hiding a tab does not avoid this server work.

First identify repeated queries and share exact request-scoped positions, policies
and evidence under existing prepared-input checks. Consider paged/on-demand history,
documents or other heavy secondary fragments only where measurements justify them;
each fragment must recheck Workspace access and current source/date. Preserve
useful first-render balances, action blockers, no-JavaScript access and immutable
history. Do not introduce a broad cross-request financial cache or change worker
scheduling as part of a page-speed fix.

The [dashboard queue selector](../../apps/tenant_apps/loans/selectors/counter_work.py)
currently reads all draft/approved/active rows and folds active obligation states
before paginating the selected queue in Python. The overview separately folds
active recorded-event balances in bounded batches. Existing deferred section
loading is valuable; measure these full-portfolio reads with representative history
before changing them. This review does not establish a production bottleneck or
resume the shelved monitoring load programme.

### EC-05: make the Loans list useful at a glance

At 390px width, the results heading begins around 1,022px from the top in both
synthetic lists. Export explanation, balance explanation, sort description and
mapping guidance then precede actual records. The visible row correctly labels
its amount "Principal at entry" and includes collateral, but it does not answer
what remains unpaid or offer a direct payment action.

Keep search immediately accessible and collapse contextual guidance after first
use. Show applied-filter chips and explicit Active/Drafts/Awaiting payout/Closed
views; preserve the ability to search all loans and unadmitted source records.
Distinguish a retained source claim from an admitted loan. Consider a compact
desktop table and readable mobile cards, with a short collateral summary.

For supported active loans, offer principal pending, interest pending and total to
collect using shared summary semantics, as-of time and clear unavailable states.
Decide row density/optional columns from counter use; avoid putting every Excel
column on a phone. Page-bound and measure calculations before enabling money on
every row. A payment link opens the ordinary reviewed action; it performs no
one-click financial write. Keep the existing filtered Excel export.

### EC-06: reduce entry friction while preserving one shared editor

The phone captures measure about 3,187px for default direct entry and 4,182px for
paper as a standing default (4,376px when explicitly overridden). These are fixture
observations, not universal sizes; names, setup and conditional fields change them.
The item summary appears after form actions on a phone. Paper entry exposes current
monitoring/reference explanation during routine original-fact capture.

Keep borrower, series, original/proposed date, item facts and amounts prominent.
Use configured product/tenure/rates when unambiguous and permitted, with explicit
override access; never infer historical facts merely to fill a field. Collapse
non-actionable policy/reference explanation while leaving genuine missing setup or
unsupported terms clear. Keep item additions, quantity/weight meaning and total
principal understandable. A compact persistent summary/action area should avoid
covering fields, errors or the on-screen keyboard.

Add a navigation warning for unsaved edits first. Direct Save draft already exists;
do not invent another loan state or silently post a paper loan as an autosave.
Preserve existing in-page mode-switch/photo retention and explicitly handle reload
file re-selection. Do not persist borrower/loan facts in browser storage by default.
A later explicit "Record and enter next" may retain series/entry preference after
success while clearing borrower/item/amount facts and issuing fresh review/idempotency
tokens; it must not let the previous loan's review confirm another loan.

### EC-07: dashboard as the start of daily work

Keep search and New loan first, plus deferred queues/overview and loading/retry
states. Add a compact daily summary of actual loans issued and receipts collected
(principal/interest/fees) with traceable links, separate from scheduled payments
and today's corrected historical activity. Define effective-date versus recording-date
meaning and reversal handling. Actual cash, paper proceeds and amounts carried at
an opening must retain their different evidence limits; do not call portfolio
balances or scheduled debt "cash collected".

Provide a short priority work preview: due/overdue, awaiting payout and drafts to
finish, linking to existing complete work pages. Presently overdue is the first
default queue when nonempty, but [_dashboard_queues.html](../../templates/company/_dashboard_queues.html)
omits its inline table and sends staff to a dedicated overdue page. A bounded
preview can make that extra step optional. Keep schedule-review exclusions visible;
unknown schedules must not become zero overdue. Detailed portfolio/risk diagnostics
remain available below the counter work rather than displacing it.

## Local evidence and limits

Three isolated synthetic review tests pass in 14.299 seconds, using only
`test_rokkad_architecture_snapshot_20261016` and fixture records. Nine rendered
states at widths 1365 and 390 give **18 browser states**, with no observed
horizontal page overflow, duplicate IDs or script errors. All six detail tabs
are exercised for native and paper loans at both widths: 24 tab selections.
Representative entry/list/detail screenshots are inspected.

The browser uses captured Django responses, existing local static files and cached
Bootstrap; all requests are intercepted. Direct price preflight uses a captured
local response. Unsupported network interactions, real uploads/cameras, keyboard
hardware and production end-to-end latency are not claimed. Full dashboard render
and section HTTP reads are reviewed; its default asynchronous network journey is
not benchmarked. Fixtures include a current quote, a supported native active loan,
paper active loans, a draft and optional unconfirmed book assurance.

| Captured GET | SQL queries | Local elapsed ms |
|---|---:|---:|
| Direct entry | 129 | 292.36 |
| Paper entry, standing default | 95 | 91.04 |
| Native filtered list | 85 | 128.51 |
| Paper filtered list | 87 | 80.14 |
| Native active detail | 275 | 442.91 |
| Paper active detail | 303 | 553.87 |
| Full dashboard | 81 | 154.35 |
| Dashboard queues fragment | 48 | 43.16 |
| Dashboard overview fragment | 42 | 64.53 |

These are one-pass local HTTP observations including shell/authorization work,
not percentiles, real portfolio sizing, production timing or restricted-role load
acceptance. The separate requests must not be added as a single page-load total.
Research scripts, captured HTML, screenshots and structured evidence remain in
ignored `.tmp/everyday-loan-review-20261016/`. Subsequent implementation should
add focused semantic/navigation/query tests for its specific changes; existing
financial, permission, isolation and source-binding safeguards remain required.

## Recommended next increment

Implement EC-01 and EC-02 first, then EC-03 and a measured EC-04 pass. Follow with
the compact list and entry improvements; add daily collection reporting after its
event/date/amount definitions are agreed. This order corrects misleading information
and establishes a read-cost budget before adding richer amounts to high-traffic
pages. Recommendations are proposed, not selected implementation or deployment.
This review changes no application source, financial record, production data,
policy, worker, notification, commit or release.
