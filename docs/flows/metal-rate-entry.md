---
status: active
owner: rates
updated: 2026-09-11
tags: [rates, setup, operator, valuation]
---

# Enter and correct metal prices

Open **Rates** in your Workspace, or use **Review metal prices** in business setup.
A source identifies where you obtained a price; creating a source alone does not
supply a price for a loan.

1. Add a source if needed, with its name and location. The source's tax flag only
   describes its published prices; Rokkad does not calculate a tax adjustment.
2. Select **Add Rate**, source, metal and currency. For loan valuation select
   **INR** and **Pure metal (100%)**, including for silver. Enter an item's actual
   purity separately on the loan; do not enter an ornament's price as pure-metal price.
3. Enter positive buying and selling prices **per gram**, excluding taxes and
   making charges. Buying price is used for collateral valuation. Selling price
   is reference information. Convert a price per 10 grams by dividing by 10, or
   a price per kilogram by dividing by 1,000. These are unit conversions only;
   obtain a pure-metal quote rather than guessing a purity or tax adjustment.
4. Set **Effective at** to when that price applied, in local time. A new blank
   effective time uses now. Rokkad separately records entry time and your identity.
   A future-effective quote is retained but does not supply today's earlier lookup.
5. Save and review the price, effective time, source and record status. Loans chooses
   the latest applicable INR pure-metal buying quote across sources; ties use entry
   time and then record ID. Date-only loan checks include the whole selected local day.

To fix a mistake, open the quote and select **Correct rate**, change the incorrect
fields and enter a reason. Saving creates a new linked record; the previous values
remain visible. Use **Add Rate** for a genuinely new market observation, and
**Correct rate** to replace an erroneous observation. Follow the previous/next
record links to inspect the correction chain.

Use **Withdraw** from the list when a quote should no longer be used, and provide a
reason. Withdrawal keeps the original and its history. An earlier independent quote
may become applicable again. A source with quote history cannot be deleted.

If a loan form reports a missing price, keep that form open, add the quote in its
Rates tab, return and select **Check prices again**. The effective date must cover
the loan date. Manual appraisals stay unchanged; use the appraisal suggestion
explicitly if you want to adopt the updated estimate.

Older migrated quotes preserve their values and original dates. Their author is
shown as unknown, and their source snapshot was captured at migration. Verify their
units, purity and tax basis before relying on them; use a correction when necessary.
Current-loan monitoring enforces its configured quote/appraisal age limits; see
[collateral reassessment](collateral-reassessment.md). New-loan entry checks quote
availability and does not yet enforce an origination-age policy. A recorded quote is
not a claim of a live market price or a current portfolio assessment.

See the [quote evidence decision](../adr/2026-09-11-rate-quote-evidence.md) and
[Rates/appraisal delivery review](../implementation/rates-appraisal-monitoring-review.md).
