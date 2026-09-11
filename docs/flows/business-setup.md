---
status: active
owner: project
updated: 2026-09-11
tags: [onboarding, workspace, loans]
---

# Set up your business

From My Workspaces, choose **Set up your business**. The existing creation service
creates the Workspace and Owner membership, then opens that business's setup page.
There is no new tenant model or separate onboarding wizard to synchronize.

The setup page shows business details, license, numbering series, calculation and
interest policies, an active loan product, and an active borrower. **Continue setup**
links to the first unavailable step. Each step uses its existing form and service.
After saving, use **Business setup** in the loan setup navigation, or return through
Settings → Setup. Reloading or returning after signing in derives progress from saved
records; reading the checklist does not create records or consume numbers.

An available step is a configuration check as of today, not a certification of
regulatory compliance or approval for an individual loan. Review license evidence,
metal buying rates, terms and document output. Commands retain final validation.
Loan product and policy effective dates still matter. Invalid or incomplete settings
can become unavailable again when dates or configuration change.

**Metal valuation prices** shows gold/silver quote availability and dates using
the same lookup as loan valuation. A source alone does not complete the general
Rates task. The lending checklist can be ready for one supported metal or an
appraisal-only policy; it does not require silver to originate a gold-only loan.
The price step guides setup rather than blocking the form before the user selects
a series, loan date and collateral metals.

On the new/edit loan form, **Metal prices for this loan** checks that actual
selection. With JavaScript/HTMX available it checks again before Save/Preview,
without uploading borrower details or files. Missing prices keep the existing
page and file inputs in place. Open Rates in another tab, add the needed quote,
return and select **Check prices again**. This also refreshes appraisal suggestions
without overwriting manual values. Manual appraisal alone cannot satisfy a
lower-of policy that also requires a metal price.

The current quote contract is a positive INR buying price per gram of pure metal,
labelled **Pure metal (100%)** for both metals, effective on/before the loan date.
The compatible storage key remains `24k`. Quote entry separates effective time
from recorded time and preserves corrections/withdrawals as linked history; see
[entering metal prices](metal-rate-entry.md). Dates are visible; a usable lookup
does not yet enforce an origination-age policy. Active-loan monitoring separately
enforces the configured quote/appraisal ages; see [reassessment](collateral-reassessment.md). An appraisal-only
policy bypasses the price requirement. Server commands always revalidate; without
JavaScript, or if evidence changes after preflight, normal server form errors apply
and new photo uploads must be reselected after the response reloads the page.

Economic forms retain editable defaults: gold 2% monthly, silver 4% monthly, and a
separate fixed INR 10 document fee deducted at disbursal. **Business default (all
licenses)** remains the default policy scope. Selecting a license creates an override;
the presence of only one license does not silently change the policy's scope. Saving
requires explicit review/submission and never rewrites existing policy evidence.

For an unbound new-loan form:

- Select the sole active series with an active license covering the loan date and
  an available number under the existing issuance check. The selected series visibly
  identifies its license; no separate license selection is needed.
- Select the sole active product version available for that date.
- Leave multiple eligible options for the user to choose. Respect explicitly supplied
  initial selections. Never select a borrower automatically.
- Keep defaults visible and editable. Changing the loan date requires reviewing them;
  the form does not silently replace a user's selections when the date changes.
- Bound forms retain submitted values, including blanks/invalid values, for correction.
  Existing draft edits retain their fixed series/product behavior. Services still
  enforce date, lifecycle, economics, product tenure and numbering constraints.

Team invitations are optional and excluded from general checklist completion counts.
The older general checklist and its dashboard reminder controls remain in a collapsed
section. Hiding/marking that reminder complete never marks lending settings ready.
An owner can work alone; adding staff never changes the selected loan workflow.

The setup page retains settings-administration authorization. Staff without setup
access continue to receive the existing owner/admin handoff. Organization-wide access
and RLS are unchanged; optional license scoping remains deferred for separate review
and explicit owner approval.
