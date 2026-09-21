---
status: accepted
owner: project
updated: 2026-09-21
tags: [adr, migration, portability, legacy]
---

# Versioned legacy source profiles and correction ledger

## Decision

Use an explicit versioned source profile for each selected Linode tenant schema:
`linode-jcl/1`, `linode-jsk/1`, and `linode-lakshmi/1`. A profile only identifies
the source schema and approved source-only corrections. It does not certify loan
balances, interest, custody, setup or operational admission.

Corrections are an in-code immutable ledger keyed by profile, table, source primary
key, field and exact original raw value. During preview, the adapter copies source
rows, verifies the original value, applies the effective value only to the copied
review facts, and attaches the correction decision to the record. The source hash
continues to hash the unaltered source row.

## Consequences

The JCL correction for `girvi_loan:29887` / `R09911` changes its effective loan
date from `2026-12-16 09:47:00+00` to `2025-12-16 09:47:00+00` only after the
archive proves the original value. A final archive that already contains the exact
corrected value is accepted with the explicit `ALREADY_CORRECTED_AT_SOURCE` evidence
state. Any third value fails closed and requires a new reviewed ledger version.

JSK and Lakshmi profiles contain no owner financial assumptions and no corrections.
Their profile previews establish source-contract compatibility only. Active-loan
admission still requires the reviewed opening-position workflow.
