---
status: accepted
owner: project
updated: 2026-10-10
tags: [adr, portability, pc-06]
---

# Transfer wider loan graphs without transferring source authority

PC-06 follows the [completion plan](../plans/data-portability-completion-20261010.md).
The existing financial and custody graph remains the restoration boundary.
Published version-1 servicing files keep their exact inventory and meaning.

Version 2 explicitly supports actual-paper origination corrections. Every earlier
native payout must have its retained same-day compensating reversal, with exact
source IDs and hashes. Destination IDs and hashes are recalculated together;
original source evidence remains in the immutable import packet. Neutral attempts
are checked against their own frozen agreement, rather than the corrected loan's
current principal. They never become another outstanding payout.

Version 3 adds a fixed inventory of referenced physical-location ancestors and
ordered storage movements. A shared location is an ancestor, not a relationship
that pulls all its other loans into the financial graph. A source namespace and
destination Workspace derive its local scan identity. Repeated graphs reuse only
that exact identity with identical configuration; matching names or codes alone
do not authorize reuse. The movement chain starts at no location and must end at
the source projection. Custody remains independent. Destination manual transfers
continue through the ordinary Owner-authorized storage service.

A retained item may have known zero principal at an accepted opening checkpoint.
Its original positive principal, reviewed remaining zero and custody remain
explicit. Migration 0069 permits nonnegative item allocations and adds a deferred
database guard requiring the exact accepted review/4 or review/5 item mapping.
Ordinary new lending cannot create zero allocations; negative allocations and a
zero-total active loan remain invalid. No repayment or disbursal is fabricated.

Version 4 adds thirteen existing FundingLoan tables to version 3's inventory.
Funding pledges connect their pawn loans into the same bounded graph. Exact
canonical lender identities must already be imported. Independent financial folds,
original activation LTV, recording-time return balances, original custody and final
funding positions reconcile before acceptance. Funding is its own aggregate;
restoration does not turn its principal into borrower debt or repay/payout again.
Headers are inserted at the relevant original custody event. This supports an item
returned under one funding loan and later pledged under another, while preserving
the active-item uniqueness constraint. Number configuration must match and counters
can only advance. Ordinary funding repayment, return and closure services continue.

Migration 0071 corrects the deferred return check for a retained return reversal.
A reversed return requires its exact inverse custody movement and the final pledge
release/reactivation position. It also checks newly inserted reversal headers.
Unreversed returns retain the original release requirement. This is a consistency
correction for native and imported histories, not a restoration bypass.

The explicit `rokkad-business-package/2` composes these versions with a 24-model
setup contract, including all physical locations and the funding number counter.
Version 1 retains its original 22-model setup and exclusion meanings. Posted funding
without a supported connected pawn graph is held. Unconnected unpaid funding
drafts/cancellations remain an explicit exclusion; their reserved counter survives.

Source licence verification/attestation revisions become `IMPORTED_SOURCE` claims.
Licences remain inactive; the destination Owner must review/save the licence before
new lending. A source owner's attestation never becomes a destination attestation.
Legacy references that still need verification retain their ordinary verification
path. Source quote observations retain their original timestamp, effective date and
frozen source definition with bounded `rate-source-transfer/1` provenance. A later
ordinary observation uses the current RateSource definition. Neither adapter
copies setup user IDs, re-dates quotes or supplies automatic commercial approval.

Source book acceptance, future capture, staff access and commercial activation
remain independent from destination operation. Khata and physical-verification
graphs still require separate supported coverage. Final verification and production
release are recorded separately in the [implementation record](../implementation/portable-graphs-pc06.md).
