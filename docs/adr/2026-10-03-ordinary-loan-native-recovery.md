---
status: accepted
owner: project
updated: 2026-10-03
tags: [loans, paper-entry, recovery]
---

# Restore recorded history as retained native evidence

Recorded loans cannot use the approval-based complete-history importer: doing so
would invent approval and lose correction, renewal and coverage relationships.
UR-11 therefore supplies a versioned native ordinary-Loans recovery archive using
the existing Khata recovery pattern. It captures the whole Workspace's ordinary
Loans table inventory, including imported openings, recorded and approved loans,
their connected renewals, funding/storage, reviews, archive sources and file bytes.
Taking the whole connected inventory avoids silently dropping a dependency.

This is a trusted backup, not a third-party paper-history admission profile. It
preserves original primary keys, actors, timestamps, source identities and JSON
references. Restore is offline, table-owner only, into empty ordinary-Loans tables
in a matching recovered database with the original Workspace and external Party,
actor, Rates and portability identities. An independently retained checksum and
matching model/guard fingerprints are mandatory. No runtime trigger bypass or web
restore exists. Owner recovery temporarily disables only user evidence triggers
inside the atomic restore; foreign keys, checks, uniqueness and forced RLS remain.
Preview actually restores and reconciles, then rolls back. Commit refuses existing
rows/media conflicts and compares the exact restored rows and financial, coverage
and custody projections before returning. Existing document bytes remain exact.

Native recovery is deliberately distinct from cross-Workspace portability. Moving
or merging these records into a different Workspace requires a separately reviewed
identity-remapping profile; this archive must never be presented as that importer.
Full database/media backups remain necessary for external prerequisites and larger
inventories. Existing portable opening and approval-history exports keep their
published contracts and do not silently change format.
