---
status: implemented
owner: project
updated: 2026-09-13
tags: [loans, portability, contract, archive]
---

# Closed-loan source evidence: loan-closed-evidence/1

One UTF-8 JSON document, at most 1 MiB. This is an evidence-retention format with
no financial admission or servicing capability. It is separate from complete
`loan-history/1` and `loan-opening-export/1`. An operator prepares the file; the
Workspace owner reviews and explicitly accepts it. See the
[synthetic example](examples/loan-closed-evidence.json) and
[decision](../adr/2026-09-13-historical-closed-loan-archive.md).

The closed input shape is owned by
[archive_contract.py](../../apps/tenant_apps/loans/services/archive_contract.py).
The upload page provides its JSON Schema for preparation. Supplemental validation
requires raw source records to be objects, bounds nesting, rejects JSON fractional
numbers and NUL characters, and requires a canonical non-nil source namespace.

| Group | Required fields and meaning |
| --- | --- |
| Root | `profile`, `source`, `facts`, `source_records`; no other root fields |
| Source | `namespace` canonical UUID; `system` bounded source/tenant identity; `loan_id` stable source ID; `snapshot_reference` and `evidence_reference` describing the source snapshot and its evidence |
| Facts | `status` exactly `CLOSED` as the retained classification; nullable `loan_number`, `raw_status`, `borrower_name`, `borrower_reference`, `opened_on`, `closed_on`, `original_principal`, `reported_balance`, `collateral`, `payments` |
| Borrower reference | When known: exact source `system` and `id`; no destination key or automatic Party resolution |
| Collateral | Null when unknown, otherwise at most 100 rows: `description`, nullable `quantity`, `gross_weight`, `net_weight` |
| Payments | Null when unknown, otherwise at most 500 supplied claims: `id`, nullable `date`, `amount`; never creates payment events |
| Source records | 1–500 raw JSON objects preserving all other supplied fields; no binary attachments |

All keys are present even when a nullable fact is unknown. Empty arrays represent
an explicit empty source collection, not unknown history. Money/weight values use
finite nonnegative decimal strings with at most twelve integer and six fractional
digits. Dates use ISO calendar dates without a ten-year admission bound. JSON raw
numbers may be integers; fractional values must be strings to avoid float conversion.
Raw structures are bounded to depth 24. Duplicate JSON keys, non-finite numbers,
unsupported fields/types/profile and oversized documents are rejected.

Source namespaces and system strings must distinguish different source tenants.
Source IDs and names are never remapped or normalized during archival acceptance.
The same source identity may have multiple immutable snapshots. The fingerprint
covers the entire accepted document, including its snapshot reference and raw
records. Decimal spellings and nulls survive acceptance and export; only JSON key
order/spacing are canonicalized. Export has no trailing newline and remains within
the same byte bound. It is not a copy of the original file's whitespace/BOM.

Missing evidence is reported without inventing values. Identified contradictions
are review findings, not rejection of the source claim. A nonzero balance on a
closed claim does not enter outstanding-debt reports. Review findings are frozen
with local acceptance; export carries the source document and regenerates findings
on subsequent review. Local acceptance metadata and staging history remain in the
origin Workspace. No inference of source authenticity, complete payments, verified
borrower, truthful closure, current custody or operational eligibility follows.
