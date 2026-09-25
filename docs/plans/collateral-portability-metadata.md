---
status: planned
owner: project
updated: 2026-09-25
tags: [data-portability, collateral, future-work]
---

# Preserve item quantity and interest-override provenance in portable history

The current partial `loan-history/1` contract carries the agreed monthly rate but
has no piece-count or override-provenance fields. Keep its frozen schema stable.
Quantity and override evidence introduced in migration 0026 currently survive in
the database, approval snapshots and operational backups, not a complete portable
history round trip.

Add a new versioned history profile with nullable quantity, actual/policy rates,
override reason and source actor/evidence references. Retain v1 readers without
inventing counts or policy provenance. Test export/import and re-export across
Workspaces, including legacy unknown counts, zero-interest overrides, changed
policies and frozen financial reconciliations. Extend customer-facing coverage
descriptions before describing the new profile as a complete metadata round trip.
