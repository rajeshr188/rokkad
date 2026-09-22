---
status: implemented
owner: loans
updated: 2026-09-12
tags: [dashboard, metrics, loans]
---

# Business dashboard

Open the Workspace **Dashboard**. Business overview, Financial health and Lending activity appear
above the existing search and work queues, for users with the existing `data.view`
permission. These are operational lending figures, not general-ledger accounts.
Every query uses the current Workspace and its RLS context.

## Current portfolio

These cards always describe today's current portfolio; the activity date controls
do not turn them into historical portfolio balances.

| Card | Definition |
| --- | --- |
| Total customers | Distinct Party profiles with an ACTIVE CUSTOMER role or any loan history, including drafts and archived borrower profiles. Unrelated suppliers without either relationship are excluded. |
| Active borrowers | Distinct borrowers on ACTIVE loans. Each borrower counts once regardless of loan count. |
| Active loans | Loans whose current state is ACTIVE. Draft, approved, cancelled and closed loans are excluded. |
| Principal outstanding | Recorded principal still unpaid on active loans, including capitalized interest that has become principal. |
| Recorded interest outstanding | Finalized unpaid interest, after payments, capitalization and reversals. Estimated/unfinalized and future interest are excluded. A zero here does not mean that no interest has accumulated since the last finalization. |

Amounts are INR. Financial cards use the canonical
[recorded-event balance calculation](../domain/pawn-loan-financial-read-models.md#recorded-balance)
through today. No interest is finalized and no loan state changes when viewing the
dashboard. Closed-loan balances do not enter current totals.

If an active loan lacks opening evidence or its recorded balance cannot be
calculated, both portfolio money cards show **Unavailable**, with the affected
count. A partial sum is never labelled a complete portfolio total. An empty
portfolio shows zero. Counts remain available when financial evidence needs review.

## Financial health

These cards use saved assessments for today's active loans. They are separate
from the recorded balances above, which are calculated from current loan events.
The dashboard shows current, stale, unassessed and failed assessment counts and
the oldest current assessment time. Changing the activity period does not change
these cards. Viewing the page does not refresh assessments or finalize interest.

| Card | Definition |
| --- | --- |
| Estimated unfinalized interest | Canonical interest preview through the assessment date, additional to recorded unpaid interest. |
| Total economic exposure | Recorded principal, interest and fees plus that preview, all from the same saved assessments. |
| Eligible collateral value | Value accepted by each loan's valuation method, custody eligibility and monitoring evidence-age limits; may differ from raw market value. |
| Loans with collateral shortfall | Count with collateral worth less than their coverage exposure; combined shortfall sums each loan's shortfall without offsetting another loan's surplus. |

Coverage retains the existing basis: maturity payoff for bullet/flexible loans,
economic exposure for amortizing loans. It is not a formal regulatory NPA label.
Whole-portfolio financial amounts require usable current financial evidence on
every active loan. Coverage has its own completeness requirement. Incomplete
amounts show **Unavailable**; a partial affected-loan count is labelled **known**.
A successful assessment can still have unknown coverage because quotes or
appraisals are missing or outdated. Valid financial totals remain available then.

Owners/settings administrators can follow **Review Loan health** to review and
refresh assessments. Other viewers are directed to their administrator. After
this increment, older saved assessments need one refresh for the new financial
breakdown. Correct stale prices/appraisals or integrity findings through their
existing workflows; refreshing alone cannot repair them. Automatic refresh needs
the optional worker to be configured and running. See
[Loan health](loan-health-monitoring.md).

## Lending activity

Choose **This month** (default), **Today**, **Last 30 days**, or **Custom dates**,
then Apply. Custom periods include both endpoints, accept up to 366 calendar days,
and cannot include future dates. Invalid input stays visible with errors; it does
not silently select another period. Queue selection and pagination retain the
activity filter. Portfolio cards continue to show today.

- **New loans issued:** valid ordinary disbursal events effective in the period.
  Saving a draft or approving it does not count as issuing a loan.
- **Average new loans / day:** new loans issued divided by all calendar days in
  the selected period, including days with no loans and today. This is not an
  average over working days or only days with activity.
- **New-loan cash disbursed:** frozen net cash after advance-interest and fee
  deductions. Legacy principal-only disbursals use their original no-deduction
  contract. This card excludes renewal top-ups and carried-forward principal.
- **Renewals completed:** valid renewal opening events in the period, counted
  separately. A renewal never counts as a fresh ordinary loan or repeats the
  carried principal in the new-loan cash card.

Loans subsequently closed still count as historical issues. Issues reversed by
today are excluded even if their reversal occurred outside the selected period;
future-effective reversals do not remove them yet. This is a report using today's
corrected evidence, not a frozen report of what was known on the historical date.
Missing/invalid cash evidence makes the entire cash card unavailable and shows the
affected count; activity counts remain available.

## Implementation and remaining scope

`loans/selectors/business_overview.py` owns calculations. Counts use database
aggregates. Active loan/policy rows and effective-dated events are read in batches
of 250 loans and use the existing pure balance fold. Cash evidence streams in
batches of 1,000 events. There are no per-loan database lookups, persistent caches,
new tables or migrations. The recorded-balance and activity cards need no worker.
`selectors/dashboard_health.py` adds one aggregate over saved assessments and
does not recalculate health on GET. The existing projection now also preserves
the canonical interest breakdown and integrity findings under V3; see the
[decision](../adr/2026-09-12-dashboard-assessment-financial-evidence.md).

Database reads are batched, but calculation time still grows with active loans and
their event history. This does not establish launch-scale latency; the existing
[large-capacity testing deferral](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity)
remains in place. Ordinary read-committed request semantics apply; this is not a
transaction-frozen export across concurrent staff operations.

Renewal cash-flow reporting remains a separate follow-up. Automatic refresh
operator acceptance remains separate from the bounded regression checks and
does not establish launch capacity.
