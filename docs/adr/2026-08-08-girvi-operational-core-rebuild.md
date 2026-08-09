---
status: on-hold
owner: project
updated: 2026-08-08
tags: [girvi, architecture, rebuild, loans, custody, accounting]
related:
  - ../plans/girvi-operational-core-rebuild.md
  - ../domain/girvi.md
  - ../constitution.md
  - 2026-08-08-operational-accounting-integration-deferral.md
  - 2026-08-08-girvi-canonical-cleanup-and-coexistence-retirement.md
---

# ADR: Girvi Operational Core Rebuild

Date: 2026-08-08
Status: On Hold

> Paused while the Loans consolidation and Girvi retirement fit-gap evaluation
> runs. Do not implement this rebuild unless that evaluation fails on a
> fundamental product or architecture boundary and the owner reactivates this
> ADR.

## Context

Girvi accumulated its architecture while preserving production data, legacy
models, routes, status values, DEA payment evidence, and incremental migration
compatibility. Those constraints no longer apply. The resulting application
still mixes loan aggregates, computed balances, custody, lifecycle wiring,
generic accounting documents, compatibility reads, UI metadata, and posting
side effects.

The separate Loans app proved several useful design rules, but Girvi should not
become a second copy of that application. Girvi has richer established domain
knowledge for customer pawn loans, lender funding/repledge, physical custody,
release, renewal, notices, recovery, and verification. The rebuild should keep
that knowledge while replacing the implementation.

## Decision

1. Rebuild Girvi in place under the existing Django app label `girvi`, product
   identity, and URL namespace. Preserve only deliberately selected cross-app
   facade contracts and canonical route names.
2. Treat all current Girvi runtime code and schema as replaceable. Reuse a
   domain rule only after it is restated in the new domain specification and
   covered by a new acceptance test. Do not mechanically port legacy classes.
3. Build an accounting-independent operational core first. The complete loan
   lifecycle must execute with a null accounting adapter before DEA or the
   standalone accounting successor is connected.
4. Model two explicit aggregates:
   - `CustomerLoan`: money advanced to a borrower against collateral.
   - `FundingLoan`: money borrowed from a lender against selected collateral.
   Shared code is limited to true value objects and infrastructure concerns.
5. Use `party.Party` as the only borrower, lender, recipient, and counterparty
   identity. Do not retain a `contact.Customer` bridge in the new schema.
6. Store business facts as immutable operational events/documents: activation,
   repayment, accrual finalization, custody movement, release, renewal,
   funding pledge/return, recovery, write-off, and compensating reversal.
7. Keep aggregate state deliberately small. Overdue, NPA, settlement, custody,
   and balance projections are derived unless a human workflow decision must be
   retained as evidence.
8. All writes go through use-case handlers. Models enforce local invariants;
   handlers enforce aggregate/workflow invariants; database constraints and
   triggers protect immutable evidence. Views, forms, tasks, and signals do not
   perform business transitions.
9. Accounting integration consumes committed immutable business events through
   an outbound port. Accounting availability or setup never determines whether
   an operational fact can be recorded. Delivery state is not loan state.
10. Replace Girvi migration history with one clean baseline after approved
    tenant schemas are reset. No historical data migration or compatibility
    shim is required. Cross-app dependencies must be narrowed before reset.
11. Retain Girvi and Loans as independent products. This rebuild does not merge,
    transfer, synchronize, or dual-write their records.

## Layering

Dependency direction is strict:

```text
interfaces -> application -> domain
infrastructure -> application ports + domain
domain -> Python standard library only
```

- `domain/`: value objects, policies, state transitions, allocation rules, and
  pure calculations. No Django imports.
- `application/`: commands, handlers, ports, results, and transaction-level
  orchestration.
- `models/`: Django persistence mapped to durable domain facts.
- `selectors/`: read-only projections and query contracts.
- `infrastructure/`: ORM repositories, rates, notifications, documents, and
  accounting adapters.
- `interfaces/`: web forms/views/URLs, jobs, and management commands.

## Consequences

- There will be an intentional interval where the rebuild branch is not
  deployable while old schema/runtime code is removed and the new baseline is
  assembled.
- Existing Girvi data is discarded in approved schemas. Rollback is branch and
  schema-backup restoration, not row migration.
- Existing broad tests are not the target contract. A smaller behavior-first
  suite replaces them as each vertical workflow is rebuilt.
- DEA-specific defects and models stop blocking Girvi operational design.
- Accounting adapters can be added or replaced without changing loan workflow
  handlers or operational evidence.

## Superseded Guidance

This ADR supersedes the incremental-stabilization and compatibility-preserving
implementation direction in the Girvi audit follow-up plan. It preserves the
business conclusions of the release/accrual boundary ADR but replaces its
current model, service, and DEA implementation assumptions.

It does not supersede the accounting constitution, tenant isolation, permanent
Girvi/Loans ownership separation, or the rule that posted accounting effects
are corrected by reversal rather than mutation.

## Acceptance

Accept this ADR only after the owner confirms the scope decisions listed in the
paired plan, especially partial release, interest policy, recovery scope,
funding-loan MVP scope, document scope, and migration-history replacement.
