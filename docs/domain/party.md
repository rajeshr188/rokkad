---
status: active
owner: project
updated: 2026-09-22
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

The customer Overview includes a private photo gallery with one default. Adding a
photo preserves earlier photos and selects the new image; staff can select another
default or remove an image. Removing the default selects the oldest remaining image.
Existing profile images carry over automatically. Issued loan ticket artifacts stay
unchanged. See the [gallery decision](../adr/2026-09-25-party-photo-gallery.md).

Borrower search shows name, relation, one primary phone and one default address
(HOME preferred, otherwise the first saved default), plus the customer code. Contact
methods and addresses remain multiple with a primary/default per type.

On the isolated ticket feature, `document_selectors.document_identity` provides
authorized first-issue display facts to Loans. It requires matching Workspace
context and existing read permission. The primary phone is used; addresses prefer
the default HOME address, then a sole address, otherwise require an explicit
selection scoped to the same Party and Workspace. This does not alter defaults.
Loans stores rendered values, selected identity and any photograph checksum on
its immutable issue; Party edits do not rewrite previously issued tickets.

Borrower photos and documents use authorized application routes. Direct storage
URLs are not a substitute for access checks. See [private media](../implementation/private-media-access.md)
and [action permissions](../implementation/action-permission-review.md).

Borrower autocomplete rebuilds an authorized Workspace queryset using signed tokens,
without Redis widget state. See [cache configuration](../implementation/cache-configuration.md).
License-scoped staff access remains optional and shelved as
[FW-001](../plans/future-work.md#fw-001-optional-owner-configurable-license-scope).

Matching names do not automatically merge source customer records. Party import
now supports explicit per-batch decisions to keep reviewed source IDs separate,
with names unchanged, warnings, reasons and audit. Duplicate source IDs and stronger
identity matches remain conflicts; existing source aliases retain their normal
source/local change checks. These decisions cannot be mapping presets or identity
verification claims. See the
[name-review decision](../adr/2026-09-12-reviewed-party-name-collisions.md).


Contact methods and addresses can be ported through the staged profiles documented
in the [operator guide](../flows/party-master-portability.md#contact-methods-and-addresses-2026-09-12).
Party still owns phone/email/website validation, one primary/default per type and
primary contact summary synchronization. Imported verification claims remain
provenance, not local verification. Portable child identities survive native
child deletion as tombstones; imports never resurrect them automatically.


Identifiers without documents also use the
[staged portability flow](../flows/party-master-portability.md#identifiers-without-documents-2026-09-12).
Identifier values retain native trim/uppercase validation and per-Party/type
uniqueness. Expiry is a source date, not an imported verification decision.
Identifier writes do not synchronize Party tax summary fields. No checksum or
identity-proofing policy was added by portability.


Party business roles use the [role portability flow](../flows/party-master-portability.md#party-roles-with-explicit-type-mapping-2026-09-12).
Explicit source-role to active Workspace PartyRoleType mapping is required. Imports
preserve the native one-ACTIVE-role-per-type constraint and allow distinct inactive
or ended histories; they do not create role definitions, memberships or staff grants.


Party relationships use the [two-reference portability flow](../flows/party-master-portability.md#party-relationships-with-both-party-references-2026-09-12).
Links are directional, may be active or inactive, and are unique by from/to/type
regardless of active state. Self-links are prohibited; inverse links are distinct
and are never created automatically. Both endpoints must resolve in the current
Workspace. These links do not replace the master relation label/name. Native
form validation and shared save behavior apply; no Party rules were changed.
