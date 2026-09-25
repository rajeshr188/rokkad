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

## Choose a camera and check the printed ticket

In the collateral camera window or customer photo section, use **Camera** to
choose **Rear camera**, **Front camera / webcam**, or a named camera made available
by your browser after permission. Changing the selection while the camera is
running switches the live preview. Capture, review the photo, then save the form.
For another angle, switch cameras and retake. If permission is denied, choose an
image file instead. Available cameras depend on the device and browser permissions.

New ticket issues and reconstructed imported copies print a known quantity next
to its description, for example **Gold bangles (Qty 2)**. Quantity means pieces;
weights and amounts remain totals for the row. Old records without a known count
do not acquire an assumed count. Previously issued tickets keep their original
PDF, so their reprints retain the original formatting.

Displayed and newly printed money uses Indian grouping: **1,60,000** (one lakh
sixty thousand) and **1,00,00,000** (one crore). Whole amounts omit trailing .00;
actual paise remain, such as **1,60,000.50**. Enter amount fields as ordinary digits,
without commas; calculations and stored amounts are unchanged.
