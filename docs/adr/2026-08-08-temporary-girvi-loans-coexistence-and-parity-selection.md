---
status: superseded
owner: project
updated: 2026-08-08
tags: [girvi, loans, coexistence, parity, retirement, pilot]
related: [2026-08-08-girvi-loans-permanent-independent-coexistence.md, 2026-08-08-loans-consolidation-and-girvi-retirement-evaluation.md, ../plans/loan-operational-parity-pilot.md]
supersedes: [2026-08-08-girvi-loans-permanent-independent-coexistence.md permanence decision]
superseded_by: 2026-08-09-girvi-capability-extraction-into-loans.md
---

# ADR: Temporary Girvi And Loans Coexistence With Parity Selection

> Superseded on 2026-08-09. Loans is now the selected target platform and
> Girvi is the capability reference. The strict record-ownership and
> no-dual-write boundary remains in force.

## Context

Girvi has mature operator workflows. Loans has clearer service, evidence,
custody, correction, and accounting boundaries. Choosing only from current
feature count or architecture would ignore the other product's strength.

## Decision

1. Girvi and Loans coexist temporarily during development and parity testing.
2. Each application exclusively owns every record it creates. There is no
   transfer, synchronization, mirroring, or dual write.
3. Neither application is selected as the final product in advance.
4. Required Girvi capabilities are implemented or replaced in Loans, then the
   same operator scenarios are compared in both applications.
5. The preferred application is the one that expresses the business workflow
   most clearly while preserving audit, custody, correction, tenant, and
   accounting boundaries.
6. Retirement requires completed parity evidence, operator acceptance, and a
   separate accepted ADR. This decision does not authorize deletion today.
7. Regulatory operations, collateral photos and labels, hierarchical storage,
   physical verification, required notices, reports, statements, and documents
   block the first Loans parity pilot.
8. Bulk actions are useful but do not block the first pilot. They follow stable
   single-record commands and must never bypass their validation.

## Consequences

- Permanent coexistence is no longer the intended destination.
- Loans consolidation remains an evaluation, not a predetermined outcome.
- Girvi remains available until one product wins the parity comparison.
- Pilot readiness depends on operator capability, not only financial lifecycle
  completeness.
- Retirement scope and destructive cleanup remain prohibited until separately
  authorized.
