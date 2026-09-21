---
status: accepted
owner: project
updated: 2026-09-13
tags: [loans, portability, contracts]
---

# Own the opening v1 wire definition independently of models

The owner authorized the next portability contract slice after validation
classification. Opening export already selected explicit columns, but restore
derived their types and nullability from live Django model metadata. Changing a
model could therefore change how an existing archive was interpreted.

Freeze `loan-opening-export/1` row names, wire types and nullable values in
Loans-owned `opening_contract.py`. Export and restore share that version-owned
inventory. The decoder uses explicit scalar conversions and does not inspect
model fields or invoke their `to_python` methods. The published
[row definition](../contracts/loan-opening-export-v1-rows.json) is checked against
the executable definition. Existing complete-history v1 already has an explicit
schema and retains its current contract.

Keep the existing wire names, source-local reference scope, decimal normalization,
unknown values, bounds, manifest, hashes and nested versioned source evidence.
Do not rename fields or invent portable global identifiers in this compatibility
slice. The model-to-wire adapter still reads current model attributes explicitly;
future attribute renames must be adapted there, not propagated into v1 files.

Preserve the old decoder's accepted representations: finite decimal strings
without applying today's model precision validators, date/time parsing through
Django's standalone ISO parsers, and legacy UUID hex/integer forms. Timestamps
remain timezone-aware and not in the future; references remain positive integer
source keys; strings, integers and booleans keep distinct wire types. UUID integer
compatibility is decoding behavior, not a recommendation for new producers.
Canonical exports continue to write normalized decimal strings and UUID strings.

The typed decoder does not grant admission. Original source bindings, graph
fingerprints, supported financial calculations, destination mappings, permissions,
RLS, full rebuild/reconciliation and atomic rollback remain authoritative.
Nested JSON evidence retains its existing semantic checks. This is a frozen v1
row boundary, not a new general archive or a complete JSON Schema for all payloads.

Two synthetic exports were captured from the preceding implementation in an
isolated disposable database. The active example retains unknown valuation/gross
weight and a legacy licence reference; its manifest flag was set to false to
represent the earlier evidence-only producer. The serviced example retains full
release, concession, reversal and a subsequent release. Tests parse them without
rewriting evidence, restore and re-export them with semantic equality, and verify
that changed model nullability/converters cannot reinterpret v1 data. Additional
fields and invalid values remain rejected, even with a recomputed checksum.

No migration, production import, broader servicing capability or historical-only
acceptance is included. A future incompatible wire change requires a new profile
and compatibility decision. Results are recorded in [Status](../STATUS.md).
