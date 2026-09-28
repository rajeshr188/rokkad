---
status: active
owner: project
updated: 2026-09-28
tags: [loans, staff, collateral]
---

# Enter collateral and review interest

On **New loan**, select the customer, series and loan date, then add collateral.

**How this works** opens the draft-process explanation and branch setup link.
It starts collapsed. **+ Add customer** sits beside the Customer field and opens
another tab so the entered draft stays in place. The photo rule appears in the
Collateral section.

The compact **Metal prices** row shows the current check status. **Details**
opens quote dates and policy information; **Recheck** refreshes the check after
editing Rates in another tab. Missing policies/prices, approval freshness/date
warnings and failed requests expand the details automatically. A ready price
check is not approval of the loan. Draft-saving and approval rules are unchanged.

The selected borrower's card shows recorded outstanding across all active loans
in this Workspace. Principal, interest and fees are separate; the total excludes
this new loan and unposted interest. Open **View borrower loans** for details.

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
- **Recheck** refreshes the saved buying-price and policy-rate checks.
  They also run automatically. If a buying price is missing, add it in Rates in
  another tab and recheck. This button does not fetch an internet market price.
- **Preview economics** shows each actual rate, monthly interest, valuation and
  maximum permitted amount. Review before saving/approving. Approval fixes these
  terms; later policy changes do not rewrite the loan.
- **LTV limit** appears beside the appraisal after valid weights and purity.
  It shows the policy percentage and maximum for that item's eligible valuation,
  refreshes when appraisal or principal changes, and never fills your principal.
  Missing required same-day prices leave the maximum unavailable.
- **Photographs** are optional by default. Setup administrators can require them
  under **Loan setup → Loan entry**. Drafts can still be saved without photos;
  approval, including a renewal's successor, then requires a usable photo per item.

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
