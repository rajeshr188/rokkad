---
status: accepted
owner: project
updated: 2026-09-09
tags: [media, authorization, rls]
---

# Private business media delivery

## Context

Authorized collateral routes already exist, but the development media handler
previously excluded only Notify artifacts. Borrower photos and KYC links directly
exposed storage URLs. RLS cannot authorize a raw filesystem/object-storage request.

## Decision

Serve business files through ordinary Workspace application routes, using the
existing membership and action policy plus explicit record ownership/parent checks.
Party photos and documents use Party's existing view alternatives. Preserve Loans
and Notify download policies; license scope remains deferred for owner approval.

The development raw-media handler allows only company logos and personal account
avatar directories. Business and unknown directories are denied. Keep existing file
names and records: no migration or file move is necessary. Private download responses
disable caching; Party documents download as attachments and raster photos may display
inline. Upload widgets must not publish direct storage links.

## Consequences

Existing private files remain readable through their authorized routes. Raw business
links intentionally stop working. External object storage, reverse proxies and CDNs
must enforce the same boundary; application tests cannot certify their configuration.
Public presentation media is explicitly separate from borrower/business evidence.
Already downloaded bytes cannot be recalled after membership removal.

See the [inventory and deployment acceptance](../implementation/private-media-access.md).
