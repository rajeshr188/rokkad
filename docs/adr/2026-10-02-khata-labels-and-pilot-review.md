---
status: accepted
owner: project
updated: 2026-10-02
tags: [khata, labels, physical-identity, release, rls]
---

# Khata labels and pilot review

The owner requested collateral labels and the final release/pilot readiness review
after the operator/recovery slice. Khata items retain immutable UUID identities,
physical custody and their receipt sources separately from actual debt.

Reuse `KhataDocumentIssue` and its retained private PDF storage with a distinct
`LABEL` kind and versioned `khata-label/1` payload. No new table or financial/custody
source is introduced. Migration 0040 extends the kind/source constraint and inserts
a dedicated held-item identity/custody guard. Existing A4 source/statement guards
remain intact; every document kind remains immutable on UPDATE/DELETE. Advance
the existing registry migration gate; forced RLS and file coverage are unchanged.

Support one selected held item, one combined label for all held collateral, and
one page per held item. Every page is 100 x 60 mm and retains complete description,
quantity, UUID, gross/net weights, purity, storage and custody status, with totals
by metal. Pending outgoing returns remain held and are labelled accordingly;
returned items cannot receive new custody labels. Received draft items may be
labelled without claiming an approved agreement, cash payout or statutory receipt.

Issue with a CSRF-protected POST, `data.edit`/`data.export`, current business-write
availability, workspace/account locking and a workspace-unique request UUID. Store
the original payload and bytes. Repeated requests return the same issue; later
returns do not reinterpret reprints. Downloads reuse verified private PDF bytes.
Native recovery includes labels through the unchanged thirteen-table inventory.
Its guard fingerprint requires restoring a backup against its matching schema
version, then migrating forward; do not weaken recovery to accept mismatched guards.

The QR contains an authenticated workspace route using the item/account UUID.
Scanning resolves current custody under the user's access and opens the matching
detail disclosure/anchor. No borrower identity or financial amount is encoded in
the QR, and no public verification/file route is introduced. Preserve printed
domains/routes when recovering or changing the deployment address.

Reuse the existing Unicode label fitting engine. Keep a 6 pt floor, preserve all
text and refuse oversized content rather than truncate. Combined overflow directs
operators to individual labels. Rendering evidence does not certify a physical
printer or paper QR scan; those are explicit pilot acceptance checks.

Add a read-only software assessment for the named workspace: migration, forced
RLS, current restricted-role safety, enabled source guards, retained file coverage,
available series, canonical balances and native evidence encoding/checksums. It
never activates a workspace or claims that successful checks establish owner
acceptance, a saved off-device backup or a completed restore rehearsal. An owner
database connection must fail the runtime-role check even when the application
actor is authorized.

Khata remains outside ordinary pawn statutory books/notices, auctions, renewals,
funding/repledging and historical imports. This is an explicit supported-product
boundary, not a certification of regulatory exemption for independent series.
The pilot requires workspace-specific external-record/default procedures and
acceptance of the bounded correction scope. Payout/revision/settlement/completed-
handover and complex corrections remain refused. No production rollout or broad
workspace activation follows from this local implementation.
