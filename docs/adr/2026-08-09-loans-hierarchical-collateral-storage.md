---
status: accepted
owner: project
updated: 2026-08-09
tags: [loans, collateral, custody, storage, qr, pilot]
related: [../plans/loan-operational-parity-pilot.md, 2026-08-09-loans-collateral-identity-media-and-labels.md]
---

# ADR: Loans Hierarchical Collateral Storage

## Context

Loans tracked legal custody state but not the physical Branch, Vault, Cabinet,
Box, or Slot holding an item. Custody state and physical location answer
different questions and must not be collapsed into one mutable field.

## Decision

1. Storage follows the unskippable tenant-scoped hierarchy Branch → Vault →
   Cabinet → Box → optional Slot. Services and PostgreSQL enforce parent level
   and workspace.
2. Workspace-unique location codes have immutable UUID scan identity, active
   state, and optional capacity.
3. Each collateral item has one nullable current-location projection. Null
   while held in the vault is visibly awaiting initial placement; null after
   return/disposal means it is no longer physically stored.
4. Placement, transfer, lifecycle removal, and renewal carry-forward append
   immutable movement evidence. PostgreSQL checks movement order, tenant scope,
   projection agreement, and rejects mutation.
5. Only the workspace Owner may create locations or perform manual placement
   and transfer during the pilot. Lifecycle commands may write source-linked
   storage evidence inside their existing transaction.
6. Items can be placed only in a Box or Slot. Transfer requires a reason and
   capacity is checked under locks.
7. Location labels contain tenant-scoped destination QR identity. Item and
   destination scans converge on the Owner-only transfer form.
8. Release and auction remove stored items. Renewal carries retained location
   to its successor and removes returned items; reversal carries it back.
   Other custody reversals restore items as awaiting placement rather than
   fabricating a physical location.

## Consequences

- Storage history is operational evidence and creates no accounting event.
- Legal custody remains separate from physical location.
- OP4 verification can freeze expected items from the current projection and
  reuse item/location QR identities.
