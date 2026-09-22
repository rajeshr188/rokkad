---
status: active
owner: project
updated: 2026-09-22
tags: [loans, workflow, roles]
---

# Choose a loan workflow

The loan detail page places a **Check before continuing** summary before the next
action: customer, loan date, tenure, principal, advance interest, deducted fees and
net amount to pay. Review collateral/photos through the nearby link. Draft amounts
are a current preview; approval still validates the latest evidence. On approved
loans, the breakdown comes from frozen approval evidence rather than current rates.
An unavailable breakdown is shown explicitly, not replaced with guessed deductions.

An owner opens Settings > Loan workflow (also linked in Loan setup). Choose
Owner review and disburse for a combined owner action, or Separate approval and
disbursal for separate operations. Save the choice explicitly. Adding staff does
not change it. Existing Workspaces retain separate operations until changed.

In owner mode, save a draft, open Review and disburse, check the borrower,
collateral, principal, advance interest, deducted fees, and net amount to pay.
Choose the actual disbursal date, confirm payment, and submit Confirm disbursal.
This records payment; it does not transfer money. Success opens the active loan;
Print/PDF remains available separately. A changed review or a review older than
one hour must be refreshed; repeated submission does not record a second disbursal.
For valuations using metal quotes, approval requires today's positive quotes and
today's loan/disbursal dates. A changed quote requires another review even when
its price is unchanged. Appraisal-only loans keep their existing date behavior.

Both payment forms label the effective date **Payment date** and link validation
errors to fields. Empty submissions show errors without recording payment. In
owner mode a missing/expired review needs **Refresh review** and another deliberate
confirmation; reloading never silently confirms payment. The separate-disbursal
page uses the same approved monetary breakdown as the command, which rechecks
eligibility on submission. These form improvements do not alter existing roles.

In separate mode, a preparer creates/edits the draft, an approver approves its
terms, and a disburser records payment. Roles need data view plus the relevant
data create/edit or Can approve loans / Can disburse loans permission. Owner and
Admin have approval/disbursal by default; ordinary Member does not. Assign an
appropriate role with both permissions for renewal, which activates a successor.
Assign an appropriate existing role through Team; custom role permissions are managed with
the existing Role administration. There is no requirement for separate individuals.

Switching either way preserves all history and pending states. An already
approved loan remains in the separate disbursal flow even after choosing owner mode.
If its market quote is outdated or replaced, return it to draft and obtain a
fresh approval. Old approvals lacking market quote evidence also need reapproval;
previous approval history remains intact. See [Metal prices](metal-rate-entry.md).
If a workflow changes while a review page is open, the combined submission checks
the current setting and rejects it when separate operations are required.

Deployment requires the owner-only orgs.0006 migration. It adds the setting and
permission records; no runtime web/worker role receives migration authority.
