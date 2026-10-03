---
status: active
owner: loans
updated: 2026-10-02
tags: [staff-guide, loans, rates]
---

# Earlier payouts and daily prices

The [accepted unified-recording design](unified-loan-recording.md) will extend
ordinary Loans to supported mixed paper histories without requiring original
digital pricing/policy evidence. Implementation is pending; this guide describes
the existing, narrower earlier-payout workflow and its current checks.

## Money was paid yesterday but the loan is a draft

1. Keep the actual loan date matching the customer's ticket. Do not move it to
   today to get past a price warning.
2. An administrator who can edit, approve and disburse opens the loan and chooses
   **Record an earlier payout**. This is available in either loan workflow.
3. Review the actual date, principal, interest, deductions, net cash and historical
   prices. The page identifies the earlier approval used, where available.
4. Enter why recording or correction is happening now, with the paper ticket or
   other reference when available. Confirm cash was already paid on the shown date.
5. Submit **Confirm and record earlier payout** once. This activates the loan and
   records the earlier payout; it does not pay the borrower again.

If a payout is already recorded, use its existing eligible reversal first, reopen
the draft, correct the details and review. Earlier events and printed tickets stay
in history. Missing or withdrawn historical evidence needs administrator review;
entering today's price does not repair that absence. Imported old loans use the
separate migration/servicing workflows.

## Money has not been paid yet

For an **approved** loan whose prices are no longer current, choose **Review
updated valuation** in Recommended next step or on the disbursal screen:

1. Compare previous and current prices, dates, each item's lending limit,
   interest, deductions and net cash. Expand the policy/fees comparison as needed.
2. If a price is missing, add or confirm it in Rates and refresh the review.
   If LTV is exceeded, return to draft and correct the proposed loan with today's
   date. The system does not automatically lower principal or relax a limit.
3. A user with edit and approval permission confirms that cash has **not** been
   paid and accepts today's date and shown terms, then chooses **Confirm updated
   approval**. Changed prices or terms require a fresh review.
4. Check/print the new approved ticket and complete the separate disbursal step
   after payment. Reapproval itself does not record a payout. The number stays
   the same, with previous approvals and tickets preserved.

If cash was actually paid on an earlier day, do not use updated valuation.
Return an approved loan to draft with a reason, retain the actual date, and use
Record an earlier payout. Editing correct historical details is unnecessary.

An overnight draft still has its original date. Edit it to the intended payment
date, save and review the recalculated terms. Use the ordinary review/disbursal
workflow after payment. Do not attest an earlier payout for an unpaid draft.

## The metal price has not changed

Open **Rates** in the correct workspace. Under **Today's lending prices**, check
the displayed buying price, selling price, source and previous effective date.
Choose **Confirm gold/silver price unchanged for today** for each required metal.
If either price changed, use **Add Rate** instead.

Confirmation appends today's dated quote under your signed-in identity and links
the previous quote. It preserves historical values. Repeating a confirmation
does not create another quote; if another user changed prices, reload and review.
Each branch confirms its own prices. This is a human affirmation, not a live feed.

Ordinary metal-valued lending still needs today's quote or explicit confirmation.
Appraisal-only lending does not require it; payments and closures are unaffected.

## Who performed the action?

The loan Overview shows **Draft created by**, **Latest approval by**, **Payout
recorded by**, their recording times and **Actual payout date**. Loan history
shows actors and reasons for corrections. A recording user may differ from the
person who physically handed over cash. Missing legacy identities remain labelled
as unrecorded, rather than attributed to whoever is currently viewing the page.
