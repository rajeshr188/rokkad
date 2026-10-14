---
status: accepted
owner: project
updated: 2026-10-14
tags: [loans, paper-entry, corrections, party]
related: [2026-10-03-recorded-contract-corrections.md]
---

# Correct an active paper loan's mistaken borrower selection

The owner requested correction of the borrower selected during paper entry.
Reopening a completed origin as a draft would discard its lifecycle meaning.
Borrower identity correction changes the current Party association without a
financial compensation: amounts, source events, schedules and collateral are
unchanged. The service appends a typed BORROWER_CORRECTED LoanChangeLog entry
and updates the current association atomically. This is correction of an entry
mistake, not assignment of debt to another person or a Party master merge.

Reuse the existing Workspace administration and data.edit actions, Party picker,
loan aggregate lock, signed one-hour review and request-key retry pattern. The
review binds the original/target Party identities and displayed names/codes/status,
current transaction fingerprint and latest correction. Confirmation rechecks
authority, writable commercial/lifecycle access, eligibility and active target
Party in the same Workspace. Changed facts require another review. Migration
0075 protects these appended logs from UPDATE/DELETE, validates scoped Party/loan
anchors, deduplicates requests and refuses downgrade with retained corrections.
Referenced former/current Party identities cannot be deleted or moved to another
Workspace. Party names/contact details retain their ordinary edit workflow.
There is no new table or RLS registry entry.

The supported boundary is an active admitted paper anniversary loan with its
collateral held in the vault and supported receipts/accruals. Known renewal links,
auction evidence and funding pledges require a wider reconciliation; do not change
only one borrower of a connected agreement. Native loans, imported outstanding
openings and closed paper agreements retain their existing workflows.

Current borrower lists/portal authorization follow the corrected Party. Old events,
issued artifacts and consent remain intact. New contract/receipt copies identify
the borrower correction and its audit source. Existing transaction fingerprints
include borrower_id, so paper-book coverage and queued reminder evidence become
outdated; existing PawnLoan source invalidation makes monitoring stale. Confirm
paper transactions again and independently check the correct Party's consent
before preparing a new reminder.

Published cross-Workspace loan-history and servicing-bundle profiles cannot map
both former/current Party identities embedded in this evidence. They explicitly
refuse these histories; exact Workspace recovery retains all original identities
and the complete audit. Add a separately versioned remapping contract when needed,
rather than silently removing the correction or interpreting the former borrower
as the destination's current customer.
