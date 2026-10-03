---
status: proposed
owner: loans
updated: 2026-10-01
tags: [loans, khata, screens, design-review]
related: [khata-agreements.md, ../adr/2026-10-01-khata-agreement-design.md]
---

# Khata screen and calculation review

Screen design proposal. The backend foundation/calculator is now implemented
locally after the owner's instruction; no screens or production setup are enabled.
The [opening backend](../implementation/khata-opening.md) now also supports custody,
approval and withdrawals; the screens below remain proposed.
The [ADR](../adr/2026-10-01-khata-agreement-design.md) records confirmed rules;
the [scenario plan](khata-agreements.md) remains the full decision inventory.
Screen names and recommendations below are not yet approved implementation.
The [delivery design](khata-delivery-design.md) maps this proposal to repository
boundaries and phases. The owner explicitly accepted D1-D5 on 1 October 2026;
screen arrangement and implementation architecture remain proposals.
The [technical design](../architecture/khata-technical-design.md) now maps the
screens to records, action permissions, pending handovers and atomic commands.

## Layout direction

Keep the existing Rokkad colours, compact header/footer and familiar form controls.
Use short inline hints and a keyboard-accessible Bootstrap help drawer for process
explanations. Essential amounts, warnings and blocked-action reasons stay visible;
do not put them only in tooltips. Forms open as full pages, with a clear return
link to the account. Avoid many stacked modal dialogs.

Offer a Khata entry under Loans, sharing borrower search and workspace context.
Select a workspace-owned khata series; display its licence only when associated.
Series setup supports an optional licence and explains that the association,
including none, freezes when the first account number is issued.
Keep the four existing repayment products unchanged. In shared directories and
borrower history, label khata explicitly and show actual debt, not the limit as
principal. A separate khata series is confirmed; concrete sequence integration
remains design work and must not alter ordinary loan counters.

## 1. Khata list

Search by account number or borrower. Filter active/settled, overdue interest,
coverage warning, licence (including "No licence associated") and series. Paginate and support date sorting using
existing project patterns. Display columns:

| Account | Borrower | Agreed limit | Principal outstanding | Interest due | Next due | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| KH-EXAMPLE | Example borrower | INR 1 crore | INR 60 lakh | INR 0 | 10 November 2026 | None |

Primary action: **New khata**. Status/flags use text as well as colour.
An account can be active and overdue; overdue is not a replacement lifecycle state.

## 2. New khata and first withdrawal

Three compact sections:

| Section | Visible inputs or information |
| --- | --- |
| Borrower and agreement | Borrower, existing outstanding hint, khata series, associated licence when present, agreed limit, monthly interest percentage, Monthly/Annually payment, agreed LTV |
| First collateral and withdrawal | Item rows, metal, quantity, gross/net weight, purity, appraisal, photos under the existing workspace policy, first withdrawal amount |
| Review | Agreed limit, actual payout, initial coverage, monthly interest amount, first due date and full first-month minimum |

No maturity-date field. Label the rate **Interest rate (% per month)**.
Show separate figures: "Agreed limit INR 1 crore; withdrawing INR 20 lakh".
Explain next to the interest amount: "Interest is based on the full agreed limit".
Annual selection shows the expected full-year amount if limit/rate remain unchanged.

Save draft and review/approval use existing authorized workflow patterns.
Existing authorised loan approvers approve opening and limit/rate changes.
Routine entries use today's business date in the first version; no historical
import or unrestricted backdating controls are offered.
Drafts may contain incomplete collateral. First confirmed withdrawal establishes
the interest start date; draft preparation and approval alone do not.
Show "Not started" for due dates until the first withdrawal date is established.
Do not manufacture a first-month deduction from the payout.

## 3. Account overview

Static wireframe; all figures are fictional and illustrate separate values:

```text
KH-EXAMPLE  |  Example borrower  |  Active
1% per month  |  Pay monthly on the 10th  |  No fixed maturity

Agreed limit       Principal outstanding    Drawable now       Next interest due
INR 1 crore        INR 60 lakh              INR 20 lakh         INR 1 lakh / 10 Nov

[Record withdrawal] [Receive interest] [Collateral actions v]
[Change agreement]  [More: statement / settle / authorized corrections]

Overview | Collateral | Interest & payments | Agreement history | Documents
```

For this example, held value is INR 1 crore at 80% LTV: it supports INR 80 lakh,
leaving INR 20 lakh additional collateral-backed availability. Unused contractual
entitlement is INR 40 lakh. Therefore drawable now is INR 20 lakh, subject to
other restrictions. Show this explanation beneath or on expansion of the figure.
Do not equate unused entitlement with drawable cash.

Display "Interest due now" separately from next-period estimates and settlement
interest. Annual accounts must not be marked overdue monthly. Show exchange or
coverage warnings above the actions, including the owner's active warn/block mode.
If blocked, display a reason with the corrective action; warning mode leaves
the permitted action available without adding mandatory owner approval.

Overview shows recent activity only. Full histories are paginated in their tabs.
On narrow screens, cards stack and the actions wrap. Keep the full explanation
under a "How khata works" help drawer to avoid clutter.

## 4. Receive collateral / record withdrawal

Collateral actions offer **Add collateral** and **Exchange collateral**.
Receiving items never creates a payout. After a deposit, a link can open a
separate withdrawal review populated with current coverage.

Withdrawal review shows requested amount, actual principal before/after, unused
entitlement, collateral-backed availability and resulting LTV. Confirm only if
both entitlement and coverage allow it. Recheck the values at confirmation.
An owner-selected exchange warning never permits an unsupported withdrawal.
Capture the existing supported payment evidence and issue a withdrawal receipt.
No external bank transfer is initiated by this screen.

## 5. Collateral exchange

Select outgoing held items and enter incoming items, grouped by metal. Support
one-for-many and many-for-one. A gold item cannot be replaced with silver, even
in warning mode. Display current approved valuation evidence for both sides.

| Review area | Example or behaviour |
| --- | --- |
| Outgoing and incoming | Item identities, metal, weight/purity, combined value per metal |
| Difference | Outgoing INR 10 lakh; incoming INR 9 lakh; shortfall INR 1 lakh |
| Resulting account coverage | Principal, retained value, LTV before/after |
| Owner policy | Warn and allow, or disallow a failed value/LTV check |
| Outcome | Warn mode keeps confirmation available; strict mode explains what fails |

Record incoming custody before outgoing handover. A failed handover remains
pending, with both actual custody states visible. No silent item deletion or
automatic debt/interest change. A completed exchange has its own receipt and
retains the policy and valuations used. Physical readiness and authorization
remain mandatory even in warning mode.

## 6. Receive interest

Show unpaid dated interest obligations and the covered periods. Separate due,
overdue, already paid and accrued-but-not-yet-due amounts. For annual accounts,
month one is included in the annual bill; there is no separate month-one demand.
The receipt must show which periods were paid and any balance still due.

Confirmed for the first version: allocate partial payments to the oldest unpaid
due interest first. Never redirect an ordinary interest payment into principal.
Early interest payments/overpayments need a defined credit workflow before being
accepted; defer them initially rather than silently changing debt. The owner
accepted this allocation and initial scope through D4.

Overdue starts the day after the due date. Default mode warns; block mode disables
new withdrawals and exchanges but permits payments, deposits and settlement.
No penalties or interest-on-interest are created merely by a late payment.

## 7. Change agreement and reduce with return

One **Change agreement** page offers increase limit, reduce limit or change rate.
Show current/new terms, effective date, reason/agreement evidence and a short
interest comparison. Keep the account number and anniversary. Existing terms
are read-only history, not editable fields on a completed agreement.

For reductions, add an optional **Return collateral** section:

| Review figure | Example |
| --- | --- |
| Principal before / new limit | INR 1 crore / INR 80 lakh |
| Principal repayment required | INR 20 lakh |
| Held collateral value / LTV | INR 1.5 crore / 80% |
| Minimum retained collateral value | INR 1 crore |
| Selected items to return | At most INR 50 lakh in this example |

Changing selected items updates retained coverage. A failed retained-LTV check
always blocks the return, regardless of exchange warning mode. Returning items
does not itself count as principal repayment. Record actual cash settlement and
actual item handover distinctly, linked to the agreement revision.

Do not offer a standalone "return excess" action in the initial proposal.
Due/overdue interest must be cleared before a reduction return. Not-yet-due
accrued interest stays on its existing schedule, as confirmed in D5.

## 8. Settlement, history and settings

Settlement preview shows actual outstanding principal, unpaid due interest,
current-period interest, any first-month minimum adjustment, prior payments and
eligible held items. It never includes unused limit as principal payable.
Confirm payment and actual return; do not label an unpaid or unreturned account
fully complete. Exact custody/financial lifecycle mapping remains implementation
design work. Do not automatically refund a collateral shortfall as cash.

Agreement history shows revision dates, old/new limit/rate, reason and actor.
Documents retain issued bytes and links to their withdrawal, exchange, payment,
revision or settlement. A current statement is distinct from an old issued receipt.

Workspace settings expose only two confirmed operational choices:

- Exchange value/LTV shortfalls: **Warn and allow** (default) or **Disallow**.
- Overdue interest: **Warn** (default) or **Block withdrawals and exchanges**.

New settings govern subsequent operations on existing accounts; they do not
rewrite completed evidence. Same-metal exchange and reduction-return LTV are
fixed checks, not extra switches. Confirm permission mapping against existing
setup/loan authorization before implementation; do not invent a new role system.

## Five confirmed calculation/servicing decisions

The owner explicitly accepted all five recommendations on 1 October 2026.
They are confirmed khata requirements, not changes to existing flexible loans.

| ID | Confirmed decision | Concrete outcome |
| --- | --- | --- |
| D1 | Include the start/effective day and exclude the next anniversary/closure day; sum exact segments within each monthly period and round once to paise using half-up. Annual bills sum those monthly amounts. | 10 November to 25 November is 15 days; 25 November starts the new rate/limit. A payment on a due date does not start an extra day's charge for the prior period. |
| D2 | Apply the first-month minimum once per account, based on the opening limit and rate. If it closes within month one, charge the greater of that minimum and actual segmented interest to closure. Later revisions never restart it. | Opening INR 1 crore at 1% gives INR 1 lakh minimum. A mid-month increase may raise actual interest; use the larger amount, without adding a second full-month charge. |
| D3 | Preserve unused drawing entitlement through revisions: add an agreed limit increase, subtract a decrease down to zero; principal repayments do not independently restore entitlement. | Limit INR 1 crore, already drawn INR 60 lakh: INR 40 lakh unused. Reduce limit to INR 80 lakh: INR 20 lakh unused. Fully drawn INR 1 crore reduced to INR 80 lakh with INR 20 lakh repayment: no new drawable entitlement. |
| D4 | Allocate partial interest payments to oldest due interest. Initially defer early/excess payments until an explicit credit workflow is selected. | Paying INR 1.5 lakh against two INR 1 lakh dues clears the first and leaves INR 50,000 on the second; principal is unchanged. |
| D5 | Require due/overdue interest to be cleared before returning collateral during reduction; leave not-yet-due accrued interest on its existing schedule. Full settlement collects all applicable interest. | A reduction return cannot bypass old unpaid interest, but an annual payer is not forced to pay unbilled accrued months solely because the limit is reduced. |

D2 does not reduce a complete first month's actual segmented charge to the opening
minimum. A minimum is a floor, not a cap. D3 records entitlement explicitly rather
than replacing it with limit minus principal. A rate-only change leaves entitlement
unchanged. Positive availability still requires the confirmed collateral-LTV check.

## Acceptance examples to turn into tests after agreement

- Monthly and annual schedules, a 31 January start and a 29 February start.
  Propose 28 February on non-leap annual anniversaries and restoration to 29
  February in leap years; obtain agreement before fixing this edge case.
- Same-day closure: the confirmed full first-month minimum applies even if the
  chosen actual-day fraction is zero. No date convention removes that floor.
- Simultaneous rate/limit changes produce adjacent effective segments without
  overlap or a gap. Backdated changes never silently rewrite finalized dues.
- After month one: unchanged limit INR 1 crore at 1%, 10 days in a 31-day period
  gives INR 32,258.06 with D1 rounding. Annual payment does not change that rate.
- Initial rate 1%, limit INR 1 crore; 30-day first period; limit rises to INR 1.5
  crore after 15 days. Closure 5 days later gives INR 75,000 actual interest;
  D2 charges INR 1 lakh minimum. Staying the full period gives INR 1.25 lakh.
- Both same-metal grouped exchange modes; cross-metal rejection under both.
- Reduction returns must always pass LTV, including an account previously
  allowed to become undercovered through warning-mode exchanges.
- Overdue restrictions combine with exchange rules; a warning for one condition
  cannot cancel a mandatory block from another condition.
- Annual first-month minimum is included once, not demanded twice at settlement.
- Current workspace policies are rechecked at confirmation after a stale preview.
- Successful retries recover one movement/payment/revision; failures do not
  invent cash payment, received collateral or completed handover.

## What still needs design after this review

Do not call the 42-scenario inventory fully resolved. Separate numbering and
existing approver authority are confirmed. New khatas only, today-dated routine
entries, and no additional charges, penalties or funding/repledging are the
confirmed initial scope. Historical/paper import is excluded. Concrete permission
and sequence mapping, valuation freshness, corrections, default/enforcement,
native export/restore and document layouts still need bounded designs. Resolve or
defer unsupported actions visibly before implementation. In particular, do not
enable ordinary-loan auction/import/renewal code for khata by renaming a product.

After owner review, update the main plan and ADR, choose the smallest coherent
implementation scope, and prepare its architecture/test plan. Implementation and
production activation still require the later instruction described in the plan.
