---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, collection, evidence]
---

# Separate legacy interest estimates from negotiated collections

The owner clarified that collection may be 300 or 290 for the fractional-interest
example and an accepted shortfall of 50 may be treated as interest lost. Exact
fractional rounding is not a reason to delay migration preparation. This describes
negotiated collections; it does not establish a universal rounding-to-ten policy,
automatic 50-rupee tolerance, principal forgiveness or actual historical receipts.

For the offline rehearsal, choose a deterministic calculation baseline: sum the
reconciled item monthly charges without rounding, multiply by additional months
under the established inclusive anniversary rule, then round the aggregate once
to whole rupees with HALF_EVEN. This is an implementation choice under the owner's
direction to proceed, not a claim about each historical negotiation. Preserve the
unrounded value, adjustment and calculation identity. Source facts remain unchanged.

Use explicit source profile `jcl-owner/2` and calculation identity
`original-anniversary-upfront-inclusive/2`. Keep version 1 available with its
previous whole-rupee-only behavior; scope both versions to the same reviewed
namespace and tenant. No generic formula or concessions framework is introduced.

Calculated interest, actual cash interest collected and accepted interest loss are
separate facts. Preparation leaves collection/loss amounts unknown when evidence is
absent. Never fabricate historical payments or losses, erase source errors, alter
principal, or activate a loan from this calculation alone. A legacy release still
means closed according to the owner's attestation; it does not prove collection of
the exact theoretical amount. The strict complete-history import remains strict.

Current live full release requires exact settlement. Before operational use for
these migrated loans, Loans needs explicit authorized, immutable concession
evidence and settlement handling, including collector cash, interest reduction,
reason/actor, idempotency, reversal and Workspace isolation. Above-baseline
collections also need explicit treatment, not a negative loss. These are required
servicing work, not implemented or silently enabled by this offline decision.

## Authorized implementation follow-up

The owner subsequently instructed implementation to proceed. Single-loan full
release now accepts an explicit positive interest concession with a 1–255 character
reason. Reuse `loan.release` plus existing `workspace.settings.manage` for positive
concessions, including retries; ordinary exact-cash release retains its existing
permission requirement. No new roles, permission framework or automatic tolerance.

Extend the immutable release receipt's economic values with `interest_concession`
only when positive. `interest` continues to mean actual cash interest, and the
ordinary release document's settlement remains cash principal + cash interest +
cash fees. Preserve the reason in release payload metadata and the actor on the
event. Model properties expose the concession without another table or duplicated
stored totals. The canonical balance fold tracks interest conceded separately from
interest paid. Full-release schedule allocations apply cash; schedule termination
and its existing reversal remain linked to that same settlement event.

The transaction verifies cash + concession = computed total due and concession
does not exceed uncapitalized interest. Principal, capitalized interest and fees
cannot be forgiven through this field. Replay compares cash, concession and reason.
Reversal copies the original economic values, restoring paid and conceded amounts
alongside the existing custody and schedule reversal. Both UI and service enforce
reason/precision boundaries; service authorization remains authoritative.

The release form, detail and memo display the concession. Older published memo
layouts receive its amount and reason within their existing mandatory interest
binding, alongside new dedicated bindings for future layouts. Strict history export
refuses concession histories because `loan-history/1` has no loss representation.
Batch releases, ordinary repayments, renewals and above-due collection handling
retain their existing behavior. Opening import/servicing is a separate next step
under the [first-import plan](../plans/first-legacy-import.md).

See the [opening contract](../contracts/loan-opening-position-mvp.md) and
[preparation evidence](../implementation/legacy-reconciliation-worksheet.md#negotiated-collections-and-version-2-2026-09-12).
