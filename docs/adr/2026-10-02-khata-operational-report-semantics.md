---
status: accepted-local
owner: loans
updated: 2026-10-02
tags: [khata, reporting, cash, custody, corrections]
related: [2026-10-01-khata-bounded-corrections.md, ../implementation/khata-operational-reports.md, ../constitution.md]
---

# Source-backed Khata cash and current custody reports

The owner authorized the next phased improvement: operational cash and custody
reports. Existing financial sources are sufficient; no ledger, new model, charge
or posting rule is introduced. Ordinary pawn-loan reports retain their scope.

## Decision

A cash daybook selects inclusive business dates and uses corrections known at the
report's labelled knowledge date. It is not a reconstruction of what staff knew
on an earlier date. Preserve original source entries and correction links.

Withdrawals are cash out. Interest receipts are cash in unless the entire receipt
was subsequently confirmed NOT_RECEIVED, in which case the original row has zero
actual cash and the correction also has zero cash. A REFUNDED receipt remains an
original inflow; its confirmed full refund is outflow on the correction business
date. Reduction activation and settlement show actual principal received;
settlement also includes its recorded interest. Approval, accrual, proposed terms,
zero-cash revisions and collateral events do not become cash movements. Exchange
corrections remain visible as explicitly non-cash correction evidence.

This means an old cash range can change when later evidence establishes that a
receipt was never received. A refund instead affects the date cash actually left.
Show both dates and related sources so this distinction is reviewable. Historical
outstanding, opening cash balances and general-ledger reconciliation need separate
contracts and are outside this report.

Custody derives today's state from immutable receipts, active OUT reservations
and actual RETURN/HANDOVER sources across every account state. Reserved items are
physically held until handover; unopened and financially settled holdings stay
visible. Receipt-date filters select a cohort, never historical custody. Keep item
records distinct from pieces and group weights by metal. Permanent UUIDs and
exact receipt/reservation/return source links preserve identity and evidence.

Use existing data.view and report.export permissions and Workspace context/RLS.
Reports and CSV are private, read-only GETs. Filter and sort before paging;
totals include all matching sources. CSV materializes at most 10,001 matching
rows within that context and refuses more than 10,000 rather than silently
truncating. Preserve numeric amounts and escape staff text that could execute as
a spreadsheet formula. No notifications, retained report files or new dependencies.

## Consequences

Reports describe current corrected knowledge and current custody, not immutable
saved statements. Downloaded copies label their knowledge/custody date and retain
source identifiers/URLs. New compensating source kinds must define their cash and
custody treatment and extend these selectors and boundary tests before release.
Production and operator acceptance remain separate from local verification.
