---
status: active
owner: project
updated: 2026-09-08
tags: [loans, onboarding, workspace, ux]
related: [../domain/loans-regulatory-setup-and-policy.md, ../plans/workspace-navigation-simplification.md]
---

# Workspace to first loan

Workspace creation opens the explicit Workspace setup page. Existing billing
recovery still applies before ordinary business access. The page's primary
lending action opens **Settings > Loan setup**, the persistent first-loan
checklist. General Workspace checklist progress is not lending readiness;
manually marking it complete never bypasses loan validation.

An authorized owner or administrator follows the checklist:

1. Add a license, validity dates, and supporting evidence.
2. Open that license and add a numbering series with PawnLoan and release numbers.
3. Configure effective calculation and metal-interest policies; review fees.
4. Review and activate a loan product version.
5. Review metal buying rates for calculated-metal valuation. Monthly interest
   rates and metal buying rates are separate settings.
6. Review document layouts and print profiles. Built-in layouts remain available;
   custom layouts and physical print checks are not new software prerequisites.

The first four steps show availability as of today. Number previews do not
allocate numbers. Economics must resolve for the same usable series; settings
from unrelated licenses cannot be combined to satisfy this check. Product
availability uses active product/version state and its availability dates.
The license register separately reports evidence warnings. Buying rates and
documents are review tasks, not green status inferred from row counts.

Counter staff then select or add a borrower and enter the loan and photographed
collateral. The loan list and create page explain the first missing prerequisite.
Staff without `workspace.settings.manage` receive an owner/admin handoff instead
of a link to a forbidden setup page. Existing servicing remains available subject
to its existing permissions. Setup status does not override the loan command's
date, product, metal, license, economic, or evidence validation.

All links carry the explicit Workspace slug. The read-only setup selector rejects
a Workspace different from the active database context. No new models, policy
defaults, migrations, or financial commands are introduced by this UI flow.
