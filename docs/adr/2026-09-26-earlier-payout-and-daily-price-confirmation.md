---
status: accepted
owner: loans
updated: 2026-09-26
tags: [loans, rates, origination, audit]
---

# Earlier payout recording and explicit daily price confirmation

The owner approved a separate earlier-payout/correction workflow, followed by
unchanged-price confirmation, and requested correct signed-in user attribution.
This extends the September 12 origination rule; ordinary current-day lending
continues to require a same-day quote for metal-valued policies.

## Decision

- A native DRAFT with an actual payout date before today can use **Record an
  earlier payout**. Require workspace settings administration, draft editing,
  loan approval and disbursal permissions together, an active writable workspace,
  a reason, and explicit confirmation that cash was already paid. This applies
  to both simple and separate-approval workspaces. It is not legacy import.
- The actual date is the saved loan date and cannot be edited in confirmation.
  Approval, event and audit timestamps record the real recording time. The user
  who records the fact is not automatically asserted to be the original cashier.
- Prefer the loan's earlier matching approval's policy and quote identities.
  A fallback without earlier approval resolves policies existing by the end of
  the actual date, and a positive same-day quote recorded by then. No later
  backdated quote or today's price can silently supply missing historical evidence.
  An earlier approved quote since corrected or withdrawn requires further evidence
  review; this workflow does not provide an override for known bad evidence.
- Fully itemized collateral, photos, policy rates/authorized overrides, LTV,
  principal reconciliation, licence/series eligibility and existing posting
  services still apply. Existing unitemized/import/renewal openings are excluded.
  Missing historical evidence blocks recording rather than inventing values.
- Sign the reviewed loan, actor, date, economic inputs, policy IDs, quote evidence
  and prior approval basis. Verify again under workspace/loan locks; approve and
  record atomically. Matching completed submission returns its event. A different
  attempt, changed input, invalid token or changed permission cannot replay it.
- Corrections require the existing reversal and reopen sequence. Preserve old
  approvals, appraisals, disbursal attempts, schedules and issued PDFs; append new
  evidence. Never automatically complete a real customer's payout during deployment.
- **Confirm price unchanged for today** appends a Rate with an explicit
  `confirmed_from` relationship, actual recording user/time and current effective
  time. The user affirms both displayed buying and selling prices. Preserve the
  old quote; confirmation is not a correction or withdrawal. Normal rate-creation
  permission applies. Concurrent quote commands share the workspace lock;
  repeat confirmation returns the current confirmation without extra rows.
- A nullable protected self-FK and insert guard enforce same-workspace, unchanged
  values and actor evidence. Existing Rate rows and their frozen approval JSON
  are unchanged. Add confirmation provenance only for new confirmed quotes.
- Detail pages show the recorded creator, latest approver and payout recorder,
  with their own timestamps. Audit and business-event history identify actors and
  correction reasons. Unknown actors remain unknown, never replaced by the viewer
  or workspace owner. Both Tabs and Classic retain the same operational content.

## Boundaries

No automatic multi-day quote reuse, price feed or configurable freshness window
is introduced. Broader historical admission with missing records and guided
paper/Excel imports remain future work. No historical cash timestamp is invented
from a date-only record. Servicing, subscription rules and tenant isolation stay
under their existing contracts.
