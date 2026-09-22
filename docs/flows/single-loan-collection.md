---
status: active
owner: loans
updated: 2026-09-22
tags: [loans, collections, release, ux]
---

# Single-loan collections

Find the customer and loan in the correct Workspace before collecting payment.
The supported action depends on its origin, current state and staff permissions.
Imported opening loans retain their existing full-redemption support; these UI
changes do not enable separate repayments for those openings.

## Find and review the loan

Use **Loans** to search by loan number, customer name/code or phone; select a loan
status when needed. **More filters** contains license, series and loan dates.
Apply those filters, or clear them to start again. Invalid filters explain the
correction before showing results. The list's principal is the amount recorded at
creation/import; it does not state the current amount to collect.

Open the loan number, confirm the customer and review **Balances and terms**.
**Collateral and photos**, **Loan documents** and **Loan history** link to the
corresponding sections. The recommended action follows current state and authority;
**More loan actions** contains less frequent work. For an ordinary active loan,
**Collect and release all collateral** is separate from repayment. An imported
opening offers its supported full collection/release path; it does not offer auction.

## Repayment while retaining collateral

Open **Record repayment**, enter the amount received and use **Preview allocation**
to inspect the split. Preview creates no payment event. Allocation continues to
follow fees, overdue interest, current interest, then principal, with the existing
per-item principal rules. Record payment only after receiving it. The displayed
balance is recorded dues, not a full-release quote; missing balances are unavailable,
not zero. Repayment does not return collateral or close the loan.

## Full release

1. **Review the amount.** Check the customer, loan and quote date, then principal,
   interest/fees and exact settlement. Release-day interest is already included in
   interest/fees. Do not add it again. Resolve any displayed blocker first.
2. **Match the collateral.** Compare each selected item with the physical item.
   Open the collateral/photos link in another tab when needed. A retained legacy
   placeholder image remains unavailable photographic evidence.
3. **Record collection and handover.** Enter the actual cash collected. An authorized
   administrator may open Optional interest concession and enter the interest
   being forgone plus its reason. Cash plus concession must equal the current full
   settlement; principal and fees cannot be waived here. Confirm only after the
   stated cash has been collected and every listed item physically returned.

Saving runs the existing atomic release command, which recalculates eligibility
and settlement. A changed quote, invalid concession or custody blocker cannot be
bypassed by the displayed preview. Invalid forms retain input and the request key;
linked errors focus their controls and open the concession disclosure where needed.
Empty submissions record nothing. Ordinary server permissions remain authoritative
even if someone submits fields hidden by their role.

Success returns to the loan, whose release-history link leads to the release record
and memo PDF. Printing does not collect payment or perform a physical handover.
Corrections remain explicit reversals with preserved original evidence. This slice
does not change multiple-loan release, renewal, partial-release availability or
the accepted imported opening balances.
