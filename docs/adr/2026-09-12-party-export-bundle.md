---
status: accepted
owner: project
updated: 2026-09-12
tags: [adr, portability, snapshot]
---

# Bounded Party export bundle

The owner authorized the recommended export-only increment. `party-bundle/1`
packages the six released JSONL profiles with their schemas, README and manifest.
It is explicitly PARTIAL; it does not implement the proposed full Workspace archive.
No new model, migration, dependency, route or business schema is introduced.

Use the existing CSRF-protected export endpoint with `action=bundle`, preserving
Party export/read permissions and lifecycle recovery access. Materialize the ZIP
before returning any bytes. The same transaction owns identity allocation, all
six existing profile audit entries and a bundle audit entry. Any profile failure
rolls back all of these effects. No export file is retained on the server.

## Snapshot decision

The existing request already runs inside `workspace_context()` and has executed
SQL. Switching that transaction to REPEATABLE READ at this point is invalid.
Instead, stabilize the bounded source with ordinary row locks: Company first,
then Party, PartyRoleType, contact, address, identifier, role and relationship rows,
each in primary-key order. Acquire every lock before calling any profile exporter.
All lock acquisition uses NOWAIT; busy rows return a retryable export error after
rolling back the savepoint. This avoids waiting in a cycle with native Party writers
that acquired a parent row before their Workspace foreign-key check.

A full Company FOR UPDATE conflicts with the key-share checks required by every
new directly Workspace-owned row's foreign key, including checks deferred until
commit. New rows therefore cannot commit into this Workspace during the snapshot.
Existing business row locks prevent updates/deletes. Previously committed source
aliases, identities and import provenance are already immutable; child-identity
detachment requires deletion of the locked child. The snapshot instant is after
the final lock is acquired. This is a lock-stabilized committed snapshot, not an
MVCC REPEATABLE READ transaction. Manifest time is captured at that point.

PostgreSQL documents the [row-lock conflict rules](https://www.postgresql.org/docs/current/explicit-locking.html).
Restricted-role transaction tests exercise parent and child inserts, parent/child
updates, child deletion, busy-row failure and a successful other-Workspace write.
Future changes to direct Workspace FKs or evidence immutability must revisit this
proof. Company locking also briefly delays insertion of other Workspace-owned
business rows, including Loans; no table-wide lock or cross-Workspace write pause
is introduced. Locks remain held until the surrounding Workspace transaction ends.

## Bounds and coverage

Each entity profile retains its 1,000-record and 5 MiB limit; reject the entire
bundle on overflow or an existing lossless-export error. Role-type locking is also
bounded to 1,000 types. Six files allow at most 6,000 entity records and 30 MiB of
entity bytes, plus fixed schemas, README and the manifest. No chunking, background
jobs, filters or silent truncation are added.

Include empty profile files with count zero and EMPTY coverage. Manifest checksums
and sizes cover every other ZIP member; the outer SHA-256 is a response header and
audit value. Checksums establish byte integrity, not signer authenticity. The
namespace UUID is source lineage and never destination authority. Entity bytes and
identities are stable on repeated exports; ZIP metadata and captured time may vary.

At this export-only checkpoint ZIP upload was unsupported. Operators extract and import nonempty JSONL files
in manifest order, master first, through existing per-profile previews/commits.
Role types still require explicit destination mapping. Import replay/conflict rules
are unchanged; no aggregate import atomicity is promised. Exclusions include Loans,
files/KYC, Party metadata, role-type definitions, Workspace configuration/access,
presets and all other business apps. Preset transfer remains separate because
private defaults, Party references and destination role types require review.

The then-recommended validation/staging follow-up was subsequently implemented;
see [Party bundle staging](2026-09-12-party-bundle-staging.md). Aggregate commit
remains deferred; the export snapshot decision above is unchanged.
