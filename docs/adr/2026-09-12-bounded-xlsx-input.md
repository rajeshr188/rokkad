---
status: accepted
owner: project
updated: 2026-09-12
tags: [adr, portability, xlsx]
---

# Bounded XLSX input reuses the Party staging pipeline

The owner authorized XLSX after reusable mapping presets. The adapter uses the
already pinned openpyxl 3.1.5 and defusedxml 0.7.1; it adds no dependency or business
model. XLSX records enter the same staging, mapping, validation, preview, approval,
commit and canonical JSONL export path as CSV records. Source identity is unchanged
across formats when the source system, source ID and normalized facts agree.

The accepted format is deliberately one plain, visible worksheet, with unique text
headers in row 1, no more than 40 columns and 1,001 physical rows including the
header. Blank rows are skipped but their physical positions remain in source-row
provenance. Text stays exact, booleans become the existing true/false literals and
General-format numeric XML values become exact decimal text without a float round
trip. Numbers with more than 15 significant digits, date cells and custom numeric
formats are rejected. Operators supply identifiers needing leading zeros and ISO
dates/timestamps as text. No locale, date epoch or display-format guessing is added.

Before read-only openpyxl loading, inspect the ZIP directory, read bounded members
in memory and parse XML with DTD/entities/external references forbidden. Limits are
5 MiB compressed, 128 members, 16 MiB expanded total, 8 MiB per part, 100:1 expansion
per member, 200,000 XML elements and depth 64 per part. Allow only ordinary workbook,
worksheet, style, theme, shared-string and core/app metadata parts. Reject unsafe,
duplicate/case-colliding, encrypted and symbolic-link members; never extract files.
Relationships must resolve to existing allowed internal parts.

Reject formulas even with cached values, macros/disguised macro content types,
external links, attachments, hidden data, merged cells, filters, defined names,
conditional formatting and unsupported embedded features. Nondefault whole-row or
whole-column styles are also rejected rather than guessing inherited formatting.
Validate actual ordered row/cell coordinates and reset read-only dimension hints
before iteration: understated dimensions cannot silently truncate data, while
oversized declarations fail explicitly. Malformed content produces a safe error
without persisting any batch or domain row.

These choices address the library's documented [XML security requirements](https://openpyxl.readthedocs.io/en/stable/#security)
and [read-only dimension caveat](https://openpyxl.readthedocs.io/en/stable/optimized.html).
Source parser restrictions are separate from Party business validation.

Presets are format-independent tabular configurations for CSV/XLSX. Matching still
requires exact Workspace/profile/source-system/header names. Migration 0009 extends
only the existing SQL batch-preset guard to XLSX, preserving equality, ownership and
immutability checks; reversal refuses retained XLSX preset associations. The eight
infrastructure models and six released business schemas remain unchanged. JSONL
presets, workbook output, multiple sheets, archive bundles and Loans remain deferred.
See the [operator flow](../flows/party-master-portability.md#xlsx-input-2026-09-12).
