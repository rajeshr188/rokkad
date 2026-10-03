---
status: active
owner: loans
updated: 2026-09-30
tags: [loans, interest, policies]
---

# Interest policies and enforcement

Use **Loans setup > Economic setup** to review calculation policies and monthly
metal rates. These are distinct configuration sets; this guide describes application
behavior, not a legal rate limit or a change to any customer's agreed terms.

## Which setting wins

| Setting | Resolution, most specific first |
| --- | --- |
| Gold/silver monthly rate | Series, then license, then Workspace; resolved separately for each metal |
| Calculation rules | Series, then license, then Workspace (a complete policy at each scope) |

Calculation rules include simple/compound interest, the minimum first month, partial-month treatment,
advance-interest periods, capitalization interval, rounding and currency quantum.
The selected policy must be active and cover the loan date, with inclusive start
and end dates. Within the same scope, the latest effective start wins, then the
highest revision and ID. A newer Workspace policy does not override an applicable
license/series policy. A missing required policy blocks origination. Scope checks
reject a series/license outside the loan's Workspace or a series under another license.

## How a loan acquires and keeps its terms

1. Draft entry resolves the policies for the selected license, series, loan date
   and each collateral metal. Each item's allocated principal times its monthly
   percentage / 100 contributes to monthly interest. The loan-level percentage is
   a derived weighted value, not an independent editable authority.
2. Changing an item's rate override requires `loan.approve` permission and a reason,
   in addition to draft permissions. The policy rate, chosen override and reason
   remain in approval evidence. This is an explicit exception, not silent inheritance.
3. Approval resolves the applicable policies again. Changed item rates or policy
   identities require resaving the draft. Approval freezes the calculation rules,
   item principals/rates, deductions and policy references.
4. Disbursal uses the approved evidence and freezes the servicing policy snapshot.
   Later rate/policy changes do not reprice approved/disbursed loans or rewrite
   previously finalized interest. Renewal creates its own successor evidence.
5. Interest preview/finalization and collection use the loan's frozen evidence.
   Finalized accruals preserve the principal base, rate, period fraction, advance
   applied and recognized interest. Reading a preview is not a posted accrual.

Policies are created by users with Workspace settings-management authority and
business-write access. Revisions are effective-dated; changing setup is not an
authorized way to edit an existing loan's frozen terms.

## Calculation choices

- **Simple:** calculate using the applicable principal base without compound
  capitalization. **Compound:** the configured capitalization interval governs
  explicit interest-capitalization processing; merely setting the interval does
  not make a simple loan compound.
- **Minimum first month:** new setup revisions charge one full first period even
  at early closure, whether or not interest was collected upfront. Earlier frozen
  policies and imported openings retain their previous meaning. Subsequent periods
  follow the chosen treatment below.
- **FULL_MONTH:** a chargeable partial month uses fraction 1. **SLAB:** inclusive
  elapsed days up to the cutoff use the configured lower fraction; later days
  use fraction 1. A stored 15-day cutoff and 0.5 fraction do nothing while
  FULL_MONTH is selected.
- **STARTED_WEEKS:** round inclusive elapsed days up to a seven-day block, cap
  at the actual monthly period length, then divide by that period length.
- **ACTUAL_DAYS:** inclusive elapsed days divided by the actual monthly period
  length. A completed month always costs one month. Monthly periods retain the
  existing calendar-addition/clamping rule; principal remains the period-opening
  balance, not a daily reducing balance.
- **Advance interest:** zero to twelve configured periods may be deducted from
  principal at disbursal. The engine tracks application of advance interest so
  it is not charged again for the covered amount. Fees are separate deductions.
- **Rounding:** the current implementation supports rounding per accrual period,
  using the saved currency quantum and half-up arithmetic.

## Verified production configuration on 30 September 2026

| Workspace / series | Gold monthly | Silver monthly | Rate source |
| --- | ---: | ---: | --- |
| JCL, all seven active series under both licenses | 2% | 4% | Workspace |
| JSK, LINODE-1 | 2% | 4% | Workspace |
| JSK, LINODE-2 | 1.1% | 3% | Series override |
| Lakshmi Pawnbroker, all three active series | 2% | 4% | Workspace |

JSK WH (LINODE-2) uses a series calculation revision effective 30 September:
SIMPLE, minimum full first month, STARTED_WEEKS afterward, one advance period,
and paise rounding. Its 95% LTV and monthly rates are retained.
Other series retain Workspace calculation defaults: SIMPLE, FULL_MONTH, one
advance period, saved currency quantum INR 0.01. No license calculation overrides
were effective in the review. The saved
15-day/half-month and 12-period capitalization values are inactive under the
selected FULL_MONTH/SIMPLE choices. The original Workspace settings remain effective from 25 September 2026.

This table describes the current origination defaults. Imported loans retain
their reviewed source rates, opening balances and original-anniversary rules;
they are not repriced from this table. Their collection path has its own supported
opening-profile checks. Individual native loans can also retain earlier approved
rates or authorized item overrides. Inspect a particular loan's approval/disbursal
and opening evidence when explaining its actual demand.

Implementation: `services/economic_policies.py`, `pawn_economics.py`,
`pawn_drafts.py`, `pawn_lifecycle.py`, `pawn_disbursal.py`, `pawn_interest.py` and
`opening_servicing.py` under `apps/tenant_apps/loans/`. See also the
[origination contract](../domain/loans-mixed-metal-origination.md) and
[guided opening profile](guided-outstanding-register-import.md).

## Changing the treatment

Open **Loan setup > Interest & fees > Calculation rules and monthly interest**.
Use the applicable history row's **Use these settings**, check the license and
optional series scope, then choose **Charging for part of a month**. For the
half-month slab, use cutoff **15** and fraction **0.5** (day 15 is included).
Review rates and the effective date before saving. New revisions always have
one full first month minimum. Copying an older revision does not change it.

For a 30-day period after the first month and INR 300 monthly interest:

| Elapsed days | Full month | Half-month slab | Started weeks | Actual days |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 300 | 150 | 70 | 10 |
| 8 | 300 | 150 | 140 | 80 |
| 15 | 300 | 150 | 210 | 150 |
| 16 | 300 | 300 | 210 | 160 |
| 29 | 300 | 300 | 300 | 290 |

New minimum-first-month policies normalize the saved currency quantum's trailing
zeros before rounding; 0.0100 therefore rounds to paise. Existing frozen snapshots
retain their earlier precision behavior. Weekly/daily exact fractions are retained
in event evidence; accrual rows contain fixed-precision projections.
New loan-history/2 exports preserve exact weekly/daily fractions, item calculations,
advance-covered accruals and the frozen policy. Restore recalculates and reconciles
that evidence; earlier v1 files remain accepted. See the
[v2 contract and remaining scope limits](../contracts/loan-history-v2.md).
Full database backups are still required for the complete system and attachments.
See the [decision](../adr/2026-09-30-series-partial-month-interest.md).

## Help inside the app

Beside the calculation form, **How interest policies work** opens a Bootstrap help
panel. **Open guide and example calculator** provides the full guide and a read-only
illustration. The normal link still opens the guide without JavaScript.

The form hides slab cutoff/fraction unless slab charging is selected, and hides the
capitalization interval for simple interest. Existing values remain submitted and
validation errors remain visible. Before saving, review the summary of scope, start
date, first-month minimum and later treatment. This creates a revision; it does not
change existing loan snapshots.

The example assumes one unchanged principal and rate, simple interest and paise
rounding. It shows each actual calendar period, full first-month charge, applied
upfront credit and additional interest. It uses the same date/fraction/rounding
functions as servicing, but is not a real loan settlement quote.
