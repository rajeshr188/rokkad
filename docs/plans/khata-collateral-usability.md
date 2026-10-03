---
status: implemented-local
owner: loans
updated: 2026-10-02
tags: [khata, collateral, photos, search, exchange, ux]
---

# Khata collateral receiving and selection

The owner requested a lasting user/developer workflow reference and asked how to
make collateral receipt, photographs and exchange selection practical for large
Khatas, then authorized all three improvements. They are implemented locally;
see the [checkpoint](../implementation/khata-collateral-usability.md). No financial
policy or schema change is introduced. Verification/runtime identity are recorded
in that checkpoint and Status. The
[account workflow](../flows/khata-account-workflow.md) documents current behavior.

The register/detail follow-up organizes the register's four filtered financial
totals into aligned cards above filters, with matching count/range in the results
header. Detail uses Overview, Actions, Collateral, Interest, History and Documents
tabs, grouped authorized workflows and preserved QR/source/document-error paths.
This is a presentation change; the checkpoint records frozen-image and local
browser acceptance separately from production activation.

## Original limitations

Receiving an item and attaching its photograph use separate screens. Collateral
custody shows all items in an unpaginated table. Exchange uses two plain multiple
selection lists with item numbers/descriptions. It is difficult to identify similar
pieces or select a group in a large holding.

The incoming selection is essential evidence, not duplicate receipt. It links the
specific incoming group to the outgoing group, alongside current valuations and
policy warnings. The backend supports grouped replacements and excludes a prior
active incoming selection from reuse. Keep this relationship visible to staff.

## Receive an item with its photograph

Use one receiving screen with item details, storage reference, delivered-by and
a photograph upload/preview. Keep photo optional by default and clearly show the
workspace requirement. Draft preparation may omit a photo; approval and relevant
servicing boundaries retain their existing checks. Keep later photo attachment
available for items received without a photograph.

Offer **Save and add another** to support repeated receipt without returning to
the service menu. Show the new item identity and a label action after successful
receipt. Require staff to confirm actual receipt; do not infer receipt from an
exchange selection or a photographed piece alone.

Reuse existing Loans-owned receipt/photo services while preserving separate audit
sources. Validate uploads before confirming receipt and keep the upload private
through any review/confirmation step. Define rollback, file cleanup and retry
behavior so a failed upload cannot silently claim success or duplicate an item.
If saving without a failed photo is offered, make that an explicit staff choice;
never silently drop an upload. Recheck permissions, workspace and account state.

## Browse and identify many items

Add a paginated collateral browser scoped to the current Khata. Search item number,
UUID, description and storage reference. Filter metal, custody status and receipt
date; sort receipt date newest/oldest with a stable item-number tie-breaker.

Show item identity, photo thumbnail, description, metal, quantity, weights, purity,
storage, received date and custody. Access thumbnails through existing authorized
private routes. Label missing current valuations clearly rather than treating them
as zero. An individual QR remains a direct way to identify one item; do not expose
public borrower data or treat a scan as authority to release it.

Reuse existing identities and storage references; a new identifier scheme or a
new tenant table is unnecessary for this proposal. Storage references need not be
unique. Whole item records remain the unit of selection; partial item splitting
is outside this improvement.

## Select an exchange without long dropdowns

Use searchable checkbox tables for **Collateral to return** and
**Received collateral replacing it**, stacked on narrow screens. Outgoing choices
must be eligible held items. Incoming choices must additionally exclude items
already used as incoming by an active exchange. Filter returned/reserved items
out of selectable results; the browser can still show their history.

Keep a visible selected-items list with counts, identity, weights and valuations
while users search or change pages. Selections must survive navigation without
silently adding all matching results. Recheck all submitted IDs on the server.

Show selected outgoing/incoming totals by metal, replacement shortfall, retained
account cover and warnings in the final review. Do not present a one-to-one mapping
when the actual operation links groups. Do not add received incoming value to cover
twice: it already belongs to the held eligible pool.

Provide **Receive replacement collateral** from the exchange screen, returning to
the same account/exchange context afterward. Newly received items may be suggested
but staff must explicitly confirm which items replace this outgoing group. Existing
received eligible items remain available where services permit them. Receiving a
replacement is not permission to hand out the outgoing collateral.

After exchange confirmation, offer the linked actual-handover action. Keep pending
outgoing items visibly held and ineligible for new draws until handover completes.

## Acceptance for an implementation

- Combined receipt/photo succeeds once; invalid images, storage failure, retries,
  missing mandatory photos and unauthorized/cross-workspace uploads behave explicitly.
- Hundreds of fictional items can be searched and paged without loading every
  item into a select widget or serving private images through public URLs.
- Similar descriptions are distinguishable by identity, location, weights and photo.
- Selections survive search/pagination, cannot overlap, and cannot include returned,
  reserved, foreign-account or previously used active incoming items.
- Stale prices/policies/custody and repeated confirmation retain existing refusal
  and idempotency behavior. Per-metal equality, hard withdrawal LTV and WARN/BLOCK
  rules remain unchanged.
- One-to-many and many-to-one exchange history identifies both groups. Reserved
  outgoing items cease backing immediately; physical handover remains separate.
- Existing ordinary-loan receiving, photos, release and ticket behavior is preserved.

No schema or financial-contract change is needed. Combined receiving uses an
explicit actual-receipt checkbox and direct validated save, without temporary
upload staging or photo content in a review token. Exchange retains reviewed
confirmation. Changed code needs new candidate verification; the original frozen
source/image identity is preserved.
