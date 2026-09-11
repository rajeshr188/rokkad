---
status: active
owner: project
updated: 2026-09-09
tags: [domain, party]
---

# Party

Party is the canonical borrower/counterparty identity inside a Workspace, implemented
at `apps/tenant_apps/party`. Loans refers to Party; no Contact backfill or DEA account
mapping is part of the supported product. The old migration-era description is
[preserved here](../archive/context/2026-09-09/domain/party.md).

Party owns profiles, roles/relationships and private identity/KYC media. Reads and
writes require explicit Workspace context plus the existing action permissions.
Historical `contact.*` permission aliases still participate in Party authorization;
do not remove them as unused imports. Shared borrower identity does not grant
permission to perform loan lifecycle actions.

Borrower photos and documents use authorized application routes. Direct storage
URLs are not a substitute for access checks. See [private media](../implementation/private-media-access.md)
and [action permissions](../implementation/action-permission-review.md).

Borrower autocomplete rebuilds an authorized Workspace queryset using signed tokens,
without Redis widget state. See [cache configuration](../implementation/cache-configuration.md).
License-scoped staff access remains optional and shelved as
[FW-001](../plans/future-work.md#fw-001-optional-owner-configurable-license-scope).
