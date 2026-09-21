---
status: accepted
owner: project
updated: 2026-09-12
tags: [adr, portability, party]
---

# Party child profiles reuse staged import lifecycle

The owner authorized contact methods and addresses after the master slice.
They use separate `party-contact/1` and `party-address/1` profiles in the existing
bounded CSV/JSONL staging, mapping, preview, approval and atomic commit pipeline.
The frozen master profile is unchanged. Parent resolution uses exact source
aliases or a local namespace/public UUID; names and persistence IDs are not keys.

Two directly Workspace-owned infrastructure models hold typed child identities
and immutable source aliases. An optional child identity on ImportRow links each
completed result to both child and parent. Forced RLS, relationship guards and
profile checks apply in PostgreSQL. Existing batch/result immutability remains.

Native deletion of a child remains possible: its identity becomes a tombstone,
while aliases and completed provenance survive. Only actual deletion may detach
a target, checked by a deferred constraint trigger. Tombstones cannot be rebound.
Native merge/moves remain domain operations, but automatic portability identity
rewriting is deferred; replay and export of a moved identity fail explicitly.

Party owns shared form validation and contact/address save helpers. Import
requires Party edit permission and never demotes an existing primary/default of
the same type. Different primary phone types retain native source-order summary
updates. Summary changes warn before approval. Export orders summary-matching
contacts last and rejects a summary inconsistent with all primary contacts.
Source verification claims remain explicit provenance; imports do not mark local
records verified. This avoids treating external claims as local evidence.

The files remain separate bounded partial exports, not a full archive or a
cross-file transaction. Operators should export/import the related profiles
without intervening edits. XLSX, identifiers, documents, roles, relationships,
Loans and financial migration are outside this increment.

See the [operator guide](../flows/party-master-portability.md#contact-methods-and-addresses-2026-09-12)
and [delivery plan](../plans/data-portability.md).


The owner subsequently authorized identifiers without binary documents. The same
accepted design extends ChildIdentity with a nullable typed identifier target;
no new identity table or workflow is introduced. Migration 0005 extends the SQL
guards and refuses reversal after identifier identities exist. Native uniqueness,
normalization and deletion remain unchanged. Source verification timestamps remain
provenance, and nonempty identifier metadata blocks this bounded export. See the
[identifier flow](../flows/party-master-portability.md#identifiers-without-documents-2026-09-12).


The subsequent Party role slice reuses the same child identity and lifecycle.
Source role keys explicitly map to active Workspace PartyRoleTypes for both file
formats. Resolved definition snapshots participate in approval; role types are
locked and revalidated during commit. No role-definition creation or staff grants
are authorized. Migration 0006 extends the typed target and SQL guards; it refuses
reversal after role identities exist. The [role flow](../flows/party-master-portability.md#party-roles-with-explicit-type-mapping-2026-09-12)
records history, mapping and metadata limits.


The subsequent relationship slice adds party-relationship/1 with two explicit
portable master references. The existing parent identity denotes the from Party;
an immutable nullable related-parent FK denotes the to Party for this profile only.
Migration 0007 adds that FK and a typed relationship target to ChildIdentity and
extends SQL guards without a new table. The second retained identity is necessary
to detect moved endpoints on native first exports, even without source aliases.
Both endpoint bindings participate in approval and are locked during commit.
Native form validation, directional uniqueness and self-link rejection remain.
Deletion tombstones retain both endpoints; reversal refuses retained relationship
identities. See the [relationship flow](../flows/party-master-portability.md#party-relationships-with-both-party-references-2026-09-12).
