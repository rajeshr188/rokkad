---
status: accepted
owner: project
updated: 2026-09-13
tags: [loans, portability, validation]
---

# Classify portability failures without changing admission

The owner authorized audit follow-up slice 0B. Existing opening review issues and
complete-history failures need to explain whether the problem concerns document
format, missing evidence, reconciliation, or destination operation. A failure to
meet the current product contract must not imply that all source history is false.

Use four reporting categories owned by Loans:

| Category | Meaning |
| --- | --- |
| `MALFORMED_DATA` | Supplied values cannot be interpreted in the required shape, type or representation. |
| `MISSING_EVIDENCE` | Required facts, references or records are absent; unknown does not mean zero. |
| `HISTORICAL_INCONSISTENCY` | Supplied chronology, identities or amounts fail reconciliation, including comparison with the selected calculation contract. This does not adjudicate source truth. |
| `OPERATIONAL_READINESS` | The current profile, destination setup, mapping or approval does not permit the requested operation. |

Categories are descriptive metadata, never an acceptance or authorization policy.
Every existing opening issue remains ERROR and blocks document reconciliation.
The separate readiness checks remain NOT_EVALUATED even when the offline document
reconciles. Existing pending text and readiness flags remain available. No new
servicing capability is asserted.

History errors retain their exception type compatibility and original string
messages; `issue` adds category, code, field, severity and rule version. Schema
checks report the document path; command-wide checks use `document`. Existing
explicit history and setup failures have categories. Native domain/database
failures crossing the history preview boundary retain a general
`NATIVE_ADMISSION_REJECTED` operational category rather than a guessed source
diagnosis. Authorization errors continue through their existing permission path.
History upload/review displays the category; offline opening JSONL and HTML reports
include categories and summaries count issue occurrences by category.

No accepted source document, wire profile, canonical hash, signed preview payload,
database schema, financial predicate or permission rule changes. No historical
archive mode is added: a closed fact without the required settlement evidence is
still rejected. Whole-loan rollback and source evidence preservation remain required.

Validation covers missing versus malformed balances, unchanged reconciliation
gates, unresolved readiness, active/closed history round trips, unsupported old
history, missing release evidence, preservation through preview rollback, HTTP
presentation, and existing native/import/restore regressions. Delivery results
are recorded in [Status](../STATUS.md).

Next proposed work is the version-owned exchange contract in the
[follow-up plan](../plans/loans-portability-audit-followup.md), independently of ORM
fields. Historical-only persistence and wider servicing remain separate slices.
