---
status: accepted
owner: project
updated: 2026-08-07
tags: [adr, accounting, mvp, pilot]
related:
  - ../plans/standalone-accounting-mvp-readiness.md
  - 2026-08-07-standalone-accounting-transaction-kernel.md
---

# ADR: Standalone Accounting Acceptance Pilot Policy

## Context

The persisted accounting kernel is complete, but production entry remains
blocked. The project owner chose the recommended defaults rather than running a
longer decision interview.

## Decision

1. The first pilot proves accounting correctness to the owner and an accountant.
2. It uses synthetic data in a dedicated non-production tenant.
3. Sales, customer receivables, and receipts are the first workflow.
4. One owner may create, authorize, and post only inside this sandbox.
5. Production must decide and enforce maker-checker separation separately.
6. Accounting vouchers use independent sequential numbers per book and year.
7. Source-document identity remains separately preserved on every voucher.
8. The pilot does not write DEA and does not accept production events.

## Consequences

- A deterministic bootstrap and scripted harness may now be implemented.
- The harness must fail outside a clearly named non-production pilot schema.
- Sandbox success proves accounting behavior, not production authorization or
  operational readiness.
- Production facade, source adapters, migration, and cutover remain blocked by
  the K6 entry gates.
