---
status: implemented
owner: loans
updated: 2026-09-12
tags: [dashboard, metrics, loans]
---

# Business dashboard

Open the Workspace **Dashboard**. Business overview and Lending activity appear
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
new projections, new tables or migrations. No worker is needed for these metrics.

Database reads are batched, but calculation time still grows with active loans and
their event history. This does not establish launch-scale latency; the existing
[large-capacity testing deferral](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity)
remains in place. Ordinary read-committed request semantics apply; this is not a
transaction-frozen export across concurrent staff operations.

Current collateral value/coverage, projected interest, total economic exposure and
renewal cash-flow reporting are separate follow-ups. They must retain their own
freshness, completeness and financial definitions instead of reusing these cards
under broader labels.
