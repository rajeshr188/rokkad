---
status: active
owner: project
updated: 2026-09-25
tags: [loans, staff, collateral]
---

# Enter collateral and review interest

On **New loan**, select the customer, series and loan date, then add collateral.

- **Quantity** counts the pieces in that row. It starts at 1. Enter combined gross
  weight, net weight, appraisal and principal for those pieces. For example, two
  bangles weighing 20 g together use quantity 2 and total weight 20 g. Use separate
  rows if the pieces need independent rates or separate collateral returns.
- **Purity** starts at 75% for a new row. Confirm it against the actual item.
  Editing an existing item preserves its recorded purity and quantity.
- **Policy default** shows the monthly rate applicable to the chosen series,
  metal and loan date. Leave **Override monthly interest (%)** blank to use it.
  An operator with loan approval permission may enter a different percentage and
  a short reason. Zero means an explicit interest-free agreement; blank means
  policy. The override affects this item, not the branch policy or other loans.
- **Check prices again** refreshes the saved buying-price and policy-rate checks.
  They also run automatically. If a buying price is missing, add it in Rates in
  another tab and recheck. This button does not fetch an internet market price.
- **Preview economics** shows each actual rate, monthly interest, valuation and
  maximum permitted amount. Review before saving/approving. Approval fixes these
  terms; later policy changes do not rewrite the loan.

Loan detail shows the effective monthly interest rate prominently near the loan
amount. For mixed rates this is the weighted rate across allocated principal;
the Collateral tab shows each item's actual rate and override reason.

Newly generated PDFs show whole amounts without `.00`, retaining actual paise.
Previously issued PDFs reprint exactly as originally issued.
