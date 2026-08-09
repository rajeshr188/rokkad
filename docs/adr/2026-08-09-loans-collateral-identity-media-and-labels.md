---
status: accepted
owner: project
updated: 2026-08-09
tags: [loans, collateral, media, labels, qr, pilot]
related: [../plans/loan-operational-parity-pilot.md, 2026-08-08-temporary-girvi-loans-coexistence-and-parity-selection.md]
---

# ADR: Loans Collateral Identity, Media, And Labels

## Context

The first Loans parity pilot requires reliable physical-item identity. The
existing draft editor deleted and recreated collateral rows, photographs were
not required, and Loans had no item label or scan route. Attaching photographs
to that mutable row lifecycle would destroy provenance and make a printed label
unstable.

## Decision

1. Every `PawnCollateralItem` receives a unique immutable UUID `public_id`.
   Tenant-scoped routes remain the authorization boundary; the UUID is the
   durable external identity used by labels and scans.
2. Draft editing reconciles existing item IDs instead of deleting and
   recreating them. An item carrying photograph evidence cannot be removed from
   a draft; the operator must cancel and replace the draft if its identity was
   wrong.
3. New collateral entered through the UI requires one JPEG or PNG photograph,
   limited to 10 MB. The approval command independently blocks every item with
   no photograph, so service callers cannot bypass the rule.
4. Photographs are append-only immutable evidence. Each row freezes original
   filename, detected MIME type, SHA-256, byte size, actor, time, and workflow
   source. PostgreSQL rejects update and delete.
5. Approval snapshots freeze the IDs and hashes of all photographs present at
   approval. Later photographs may be appended but do not rewrite the contract
   snapshot or appraisal evidence.
6. Retained collateral in release-and-renew receives explicit inherited photo
   rows linked to its predecessor evidence. Additional collateral requires a
   fresh renewal photograph before the successor can be approved.
7. The MVP item label contains loan number, item identity, description, Party,
   net weight, and a QR code. Preview and print/reprint each append immutable
   label-issue audit evidence.
8. The QR resolves through a tenant-scoped stable scan route and opens the
   owning loan detail anchored to the item. Later storage, release, and
   verification screens may consume the same identity.

## Consequences

- Collateral identity and media are operational evidence, not mutable gallery
  content and not appraisal evidence.
- Correcting descriptive or economic draft fields preserves physical identity
  and prior photographs.
- Label generation is intentionally separate from the configurable legal
  document renderer; it is a small operational artifact with its own audit.
- OP3 storage can use the same `public_id` without inventing another item code.
