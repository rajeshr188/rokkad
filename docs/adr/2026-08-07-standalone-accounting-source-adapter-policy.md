---
status: accepted
owner: project
updated: 2026-08-07
tags: [adr, accounting, integration, idempotency, k7]
related: [../plans/standalone-accounting-k7-production-boundary.md]
---

# ADR: Standalone Accounting MVP Source Adapter Policy

## Decision

- The first adapter accepts only schema-v1 cash sale, credit sale, and customer
  receipt events in INR.
- Callers provide source identity and ledger/account keys through a frozen DTO;
  they do not import accounting models or services.
- Delivery uses the authenticated facade with distinct maker, authorizer, and
  poster actors.
- Book/source/type/id/version uniquely identifies a delivery. A canonical hash
  permits exact replay and rejects changed-payload reuse.
- Voucher creation through posting is atomic. Failure rolls back partial
  accounting while retaining retry count and bounded error evidence.
- Posted delivery identity and source evidence are immutable in PostgreSQL.

## Consequences

This is an integration boundary, not a sales UI, invoice engine, tax engine,
queue worker, or DEA cutover. Those remain outside the MVP.
