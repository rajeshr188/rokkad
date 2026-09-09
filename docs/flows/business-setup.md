---
status: active
owner: project
updated: 2026-09-09
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
