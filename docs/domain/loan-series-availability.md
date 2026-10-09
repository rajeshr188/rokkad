---
status: implemented
owner: project
updated: 2026-10-09
tags: [loans, series, numbering, paper-entry]
related: [../adr/2026-10-09-series-new-lending-and-servicing.md]
---

# Running and retained loan series

A series is a retained licence/register grouping, not the state of its loans.
**Open for new loans** controls future lending. Clear it under Loans setup, open
the licence, choose the series's **Configure**, and save. Existing records are
retained and existing loans remain available for repayments, closure, printing,
browsing and monitoring according to their own state and staff permissions.

Routine New loan displays running series: open, under a current active verified
licence, with an active loan-number sequence and an unused counter within its
maximum. The final configured number can be issued. Once the next counter exceeds
the maximum, the series disappears from routine choices automatically. Its active
flag is not rewritten. Already-numbered drafts may finish when the series remains
open; manually stopping it blocks new approval/unpaid payout. Completed retries
return the existing result. Reopening preserves all consumed/reserved numbers.

The licence's setup page retains all series and explains their current new-loan
availability. Release numbering has its own counter and readiness. An exhausted
loan counter or stopped/expired lending setup does not disable releases, but an
inactive/exhausted release sequence still needs a supported numbering decision.

In paper New loan, select **Record an earlier loan from an old series** beside
the series field to expose retained registers. Without JavaScript, use **Apply
series list** after changing this choice. A blocked direct-entry setup screen also
links to this paper path. The selected register's status is visible. Original
paper numbers stay editable. For a running register, routine paper entry initially
fills the original number and paper reference with the next automatic suggestion;
staff check them against the paper record and edit either field as needed. Untouched
suggestions follow series changes; custom values are retained. An unavailable old
register supplies no automatic suggestion, so staff enter its actual source identity.
Displaying or reviewing a suggestion reserves no number.

An unused older original number can be recorded after a range is exhausted. All
duplicate, applicable range, original-date evidence, agreement and financial
reconciliation checks still apply. Successfully recording a matching original
number at or above the counter advances it; an older one never rewinds it. The
old-series choice does not reactivate a series or claim Rokkad approved the paper
payout. Actual loan terms remain frozen by the existing admission service.

Saved drafts, source imports, archive admission and corrections retain their own
series identity and authority. Moving an existing loan to another series merely
because its register is stopped is not part of this change.
