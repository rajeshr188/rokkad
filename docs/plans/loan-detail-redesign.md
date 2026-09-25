---
status: active
owner: project
updated: 2026-09-25
tags: [loans, ux, mockups, discoverability]
---

# Loan detail layout trial

The owner prefers A (tabs) and approved trying A, B, C and the existing Classic
layout during real work before retiring any option. The initial mockups below
led to this decision. See the [trial decision](../adr/2026-09-25-loan-detail-layout-trial.md)
and [staff guide](../flows/loan-detail-layouts.md).

The implementation uses one canonical server-rendered detail record. Client-side
navigation rearranges its existing controls into Tabs, Service desk or Expandable
sections; Classic restores the previous arrangement. Tabs is the initial choice.
The selected layout is remembered separately per signed-in user and workspace in
that browser. No server preference, new database queries or schema changes are
needed. Loan calculations, permissions, submission endpoints and PDF output remain
under their existing services. Switching itself makes no request or transaction.

The initial feature map below describes the mockup. In the shipped trial,
approval review/quotes remain in Overview, payment receipts and release documents
are in Documents, collateral facts are in Collateral, and business events/audit
are in History. Errors and recommended actions remain outside the sections.
No option is scheduled for automatic retirement. Use staff feedback on everyday
printing, collection, collateral and history tasks to choose what to retain.

Interactive source: `outputs/loan-detail-mockups/loan-detail-options.html`.
It uses synthetic loan DEMO-C07550 and placeholder photographs. Actions show
local previews; they neither connect to production nor submit transactions.

## Options

| Option | Organization | Trade-off |
| --- | --- | --- |
| A: Tabs (recommended) | Identity, dates, primary actions and balance remain above six tabs: Overview, Money & interest, Collateral, Documents, History, Follow-up. | Strong fit for desktop and phone. Staff learn six stable destinations. |
| B: Service desk | The same six sections use vertical navigation beside persistent payment/release/printing actions. | Useful for repetitive counter work; consumes more horizontal space and stacks on phones. |
| C: Expandable sections | All six sections live on one page as independent accordions, with Overview open initially. | Familiar continuous record and multiple open sections; grows longer during detailed review. |

The mockups model Bootstrap tabs, vertical pills/list navigation, dropdown actions,
cards, tables, badges, alerts and accordions using scoped prototype styles. They
do not load a second Bootstrap stylesheet into the conversation. Production
implementation should reuse the application's installed Bootstrap components.

The visible example selector covers active native, draft, approved, imported,
closed and blocked-draft states. Optional design controls change spacing, sample
access and simple versus separate approval. Financial examples are illustrative;
actual rendering must retain existing selectors, calculations and permission flags.

## Feature coverage

All three options share the same content groups. Repeated summaries and duplicate
action placements may be consolidated; their underlying facts/actions remain.

| Current feature or conditional content | Proposed destination |
| --- | --- |
| Loan number, state, borrower, series prefix, loan date | Persistent identity header; DD/MM/YYYY. |
| Draft-created or imported timestamp | Overview → Loan terms, explicitly distinguished from original loan date. |
| Back to loans, previous/next in series, all borrower loans | Header navigation and borrower link. |
| Original principal, monthly rate, tenure, licence, product/version | Overview → Loan terms. |
| Sidebar collateral summary: count, metal, purity, gross/net, allocation, custody | Brief Overview summary; complete facts in Collateral. |
| Draft origination review, customer, deductions, net payout | Overview → Check before continuing; Money → Disbursal breakdown. |
| Simple owner review/disburse, separate approval, approved disbursal | State-aware primary action; separate workflow remains available. |
| Correct draft, split collateral/individual item, cancel, reopen | More actions; split also on the individual collateral item. |
| Inactive/expired licence blocker and draft transfer | Visible attention alert above the sections, with transfer action. |
| Required current quotes, recorded approval quotes and source/time links | Approval evidence and Money; Review Rates remains linked. |
| Native ticket printing, imported copy, marked imported preview | Persistent print action after eligibility; all variants in Documents. |
| Ticket history/evidence and first-issue/reprint distinction | Documents; existing administrator authority and immutable PDFs retained. |
| KFS and repayment schedule | Documents and monitoring detail; availability follows persisted schedule. |
| Record payment, collect and full release | Persistent action group or service sidebar. Existing workflow handles detailed choices. |
| Recorded principal/interest/fees/total balance | Summary strip and Money breakdown; clear as-of date. |
| Imported collection quote and blockers, maturity/grace | Money; collection calculation remains separate from recorded balance. |
| Imported elapsed months/days, charge months, upfront exclusion, next increase | Money → How interest is calculated. |
| Imported monthly/cumulative/unposted interest and post-payment principal effects | Same calculation group; never replace with a flat invented estimate. |
| Imported cutover balances, original dates, missing pre-import history | Money → Imported balance and calculation. |
| Legacy licence reference limitations | State-specific attention/record notice; no implied lending authority. |
| Balance/exposure/risk/accrual/review errors and integrity findings | Persistent attention summary with link to the affected detail; never hidden solely behind a tab. |
| Economic exposure, projected unfinalized interest, maturity payoff, due-now, overdue, cash and LTV bases | Money → Economic exposure and projections. |
| Current valuation, price/appraisal dates, ages, freshness policies and blockers | Money → Valuation and evidence; links to rates and reassessment. |
| Monitoring DPD, performance, severity, value, LTV, action hint and explanations | Money → Monitoring assessment; brief Overview summary. Closed loans stop live monitoring. |
| Accrual availability, finalize/review and conditional capitalization | Money → Interest; More actions can link to it. Compound-only rule retained. |
| Finalized accrual periods, actor/time, collection catch-up and per-item calculations | Money → Finalized interest accordions. |
| Repayment receipts, reversed badges and original-receipt evidence | Money → Payments; Documents links to receipts. |
| Collateral public ID, metal, gross/net, missing gross weight, purity and allocation | Collateral → individual item. Missing data stays explicitly unknown. |
| Draft/current appraisal and reassessment/history | Individual collateral item, with existing edit/view permissions. |
| Multiple photos, original download, source/capture time and blank legacy markers | Collateral → photo gallery/evidence. Prototype uses labelled placeholders. |
| Camera, append/upload, preview and draft-only delete | Item photo actions; existing private routes and validation retained. |
| Per-item label preview and print/reprint | Collateral → Labels & storage. |
| Custody, current storage/awaiting placement, transfer/place | Individual item plus Labels & storage. |
| Storage history: date, type, source/destination, reason/source and actor | Item accordion. |
| Unverified legacy source values/dates | Collateral → Unverified source value; distinct from current appraisal. |
| Customer notices, creation/retry, source balances/dates, channel and status | Follow-up → Notices, with expandable technical delivery evidence. |
| Notice IDs, Notify event/job, attempts/time, provider reference and failure | Notice details accordion. |
| Auction number/state/dates, buyer/recovery and cancellation reason | Follow-up → Auction recovery. |
| Initiate/start/cancel/complete/reverse auction; notice/recovery PDFs | Auction record actions, following existing lifecycle/permission checks. Imported openings remain unsupported. |
| Renewal lineage, source/successor, mode/date, principal/pay-down/top-up | Follow-up → Renewal lineage. |
| Release/renew, agreement, successor-only permitted reversal | Same renewal group; imported-opening restrictions retained. |
| Release documents, number/date/full-or-partial/amount, detail and memo | History → Release history; Documents; prominent closed-state link. |
| Business event effective date/ID, reversed-by/source/reason, eligibility/blocker | History → Business events; corrections stay attached to source evidence. |
| Audit changes, timestamp and actor | History → Audit trail. |
| Party statement and owner-only JSONL export | More actions and Documents → Records; supported-profile restrictions retained. |
| Closed-state banner and retained original terms | Header status and Overview closure summary; Documents/History remain reachable. |

## Implementation constraints

- Keep existing authoritative services, URLs, `can_*` permission flags, state
  gates, import restrictions and posting confirmations. Do not infer new
  permissions from the mockup's Owner/Read-only examples.
- Preserve section deep links from receipts, collateral, release and event links;
  selecting a hash should activate the corresponding tab/accordion.
- Keep exceptions and recommended next action visible above content navigation.
  A tab badge can supplement an error, not conceal it.
- Use an accessible tablist with keyboard navigation, unique controls/panels and
  announced selected state. Keep navigation usable when narrow and on touch.
- Avoid fetching all customer records for a tab change. Begin with current server
  selectors; consider deferred section loading only after measuring query cost.
- Preserve an ordinary server-rendered/no-JavaScript path. Do not couple
  Bootstrap navigation to financial submissions.
- Retain DD/MM/YYYY, rupee amounts, honest imported-document labels and clear
  distinction between recorded balances, unposted projection and collection quote.
- Add production-template parity tests for permission and lifecycle states when
  implementation is chosen. The owner subsequently authorized the four-layout trial described above.

## Design verification

Local Chromium checked all 108 layout/scenario/section combinations, action
previews and keyboard tabs. The prototype fits 1024, 736, 390 and 320px widths.
Desktop and phone screenshots were inspected. Generated screenshots and the
standalone preview remain under the task's output directory; no production
customer photos or database content were copied into it.
