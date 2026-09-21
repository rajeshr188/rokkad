---
status: accepted
owner: project
updated: 2026-09-12
tags: [adr, portability, mapping]
---

# Immutable Workspace CSV mapping preset versions

The owner authorized reusable mapping presets after the Party relationship slice.
The existing staged pipeline already stores exact mappings in each batch. Reuse
adds one directly Workspace-owned MappingPresetVersion table and a nullable
ImportBatch.mapping_preset reference, rather than a separate mapping engine or
mutable template hierarchy. The six released Party exchange schemas stay unchanged.

Each version stores its name, positive version number, profile, source system,
header names, complete mapping, creator and creation time. Versions are immutable
in PostgreSQL. A name identifies one profile/source-system family in a Workspace.
Saving a changed mapping or header set appends a version; saving the latest exact
configuration reuses that version. A Workspace row lock serializes version creation
and enforces the bounded 1,000-version limit. Earlier versions remain selectable.

Saving requires existing import/read permissions, ACTIVE lifecycle and the exact
reviewed approval digest from a READY or COMPLETED CSV batch. Applying requires
the same access, an unfinished CSV batch, and matching profile, source system and
header names (column order may differ). No preset selection is automatic. Applying
copies the configuration and runs the ordinary validation/preview pipeline. The
selected immutable version participates in approval; manual replacement clears
the reference. A later preset version cannot reinterpret an already approved batch.
Current Party/role-type rules and commit permissions remain authoritative.

Migration 0008 adds forced RLS, the model-specific registry gate, immutable-version
guards and a batch-reference guard checking Workspace/profile/source/headers and
exact mapping equality. Existing finished-batch guards protect retained selection
provenance. Reversal refuses to remove retained versions. Presets contain no source
rows, but explicit defaults may contain customer data and remain Workspace-private.

This increment provides no preset deletion, cross-Workspace transfer, automatic
matching, JSONL presets, XLSX parser or financial migration. Canonical export files
remain business data; presets are local configuration. See the
[operator flow](../flows/party-master-portability.md#reusable-csv-mapping-presets-2026-09-12)
and [delivery plan](../plans/data-portability.md).


The subsequent [XLSX increment](2026-09-12-bounded-xlsx-input.md) extends these same
preset semantics to XLSX as well as CSV. Version records remain unchanged;
migration 0009 widens only the batch source-type guard. The CSV-only descriptions
above record the initial preset increment.
