---
status: accepted-for-party-slice
owner: project
updated: 2026-09-12
tags: [adr, portability, imports, exports]
---

# Customer data exchange is independent of persistence

## Context

The owner requires migration from imperfect legacy records, progressive backfill,
documented export, and eventual controlled offboarding. Existing model-resource
imports and exports expose persistence structure and do not provide these guarantees.
Loans owns immutable operational financial evidence; accounting is retired.

## Proposed decision

Adopt the customer data portability principle: Workspace data belongs to the
customer, and Django/PostgreSQL schema is not the customer exchange contract.
Keep database schema, business domain, and versioned exchange schema distinct.

Use a documented Rokkad Data contract with explicit capabilities and stable opaque
identifiers. Import and export use the same entity definitions. JSON Lines is the
canonical record encoding; CSV/XLSX are adapters and readable representations.
Supporting a record in an archive does not imply permission or capability to
restore it as an operational record. Packages declare this distinction.

Introduce one small `apps/tenant_apps/data_portability` app when implementation
begins. It owns staging, mapping, provenance, identity bindings, jobs, and package
assembly. Party and Loans own validation and domain mutations. Orgs continues
to own lifecycle, ownership, and the eventual erasure authorization boundary.

Every operation names one Workspace and uses existing actor policy and restricted
RLS context. Historical migration does not replay today's financial operations,
allocate live loan numbers, fabricate historical actors, or send notifications.
Opening-position imports require a separately reviewed Loans contract before use.

Start with a bounded Party master-data vertical slice and canonical export in
the same milestone. Retire generic model write-through before exposing it.
Do not implement financial migration or physical deletion as part of that slice.

## Consequences and alternatives

- A versioned contract and conformance tests must outlive model refactors.
- Full portability needs more than customers, loans, payments, and releases:
  schedules, corrections, funding, custody, configuration, issued bytes, and
  communication evidence also matter.
- Frozen source facts and recorded-at timestamps remain separate. Insufficient
  financial evidence blocks operational activation rather than inventing facts.
- A full dump, Django serialization, or arbitrary `ModelResource` factory is not
  the contract. They cannot express deliberate import semantics or secret exclusions.
- Several new apps, a plugin registry, a general workflow engine, and a distributed
  queue are unnecessary for the initial slice.
- Legal retention rules and any privileged erasure mechanism remain decisions
  to resolve before deletion implementation; no retention duration is asserted.

The owner authorized the Party vertical slice after reviewing this proposal.
Its implemented narrowing (typed Party identity, five models, JSONL without ZIP,
and unchanged legacy tools per follow-up instruction) is recorded in the architecture.
Financial migration and erasure decisions remain proposals, not implemented guarantees.
See the [audit and architecture](../architecture/data-portability.md),
[v1 contract draft](../contracts/rokkad-data-v1.md), and
[incremental plan](../plans/data-portability.md).
