---
status: accepted
owner: project
updated: 2026-06-17
tags: [adr]
related: []
---

# Architecture Decision Records (ADR) Guide

This folder stores architecture and cross-cutting design decisions for the Rokkad codebase.

## Goals

1. Keep major technical choices explicit and reviewable.
2. Preserve rationale so future refactors do not repeat context loss.
3. Keep app boundaries and migration decisions consistent with:
   - DEA mandatory per tenant
   - notify_v2 as target system
   - event-driven, strongly consistent domain writes with eventual DEA posting

## Decision Lifecycle

Use one of these statuses in each ADR:

- Proposed
- Accepted
- Superseded
- Deprecated
- Rejected

When superseding, link both ADRs.

## Naming Convention

- Use: `YYYY-MM-DD_SHORT_TITLE.md`
- Examples:
  - `2026-05-03_GIRVI_EVENT_DRIVEN_DEA_POSTING.md`
  - `2026-05-10_NOTIFY_V1_RETIREMENT_CUTOVER.md`

Keep existing legacy decision files as-is; use this convention going forward.

## Required Sections for All ADRs

1. Date
2. Status
3. Owners
4. Summary
5. Context / Problem Statement
6. Decision
7. Rationale
8. Consequences
9. Rollout / Migration Plan
10. Observability / Guardrails
11. Alternatives Considered
12. Review Trigger

## Repo-Specific Rules

1. Any edge moving from `X` or `L` in dependency policy must have an ADR.
2. Any new async event contract requires an ADR with schema versioning and idempotency strategy.
3. Any cutover with dual-write or feature flags requires rollback criteria in ADR.
4. notify legacy changes require explicit retirement horizon and owner.

## Templates

Use templates in [docs/decisions/templates](templates):

1. `ADR_TEMPLATE.md` (generic)
2. `ADR_DEPENDENCY_EDGE_CHANGE_TEMPLATE.md`
3. `ADR_EVENT_CONTRACT_TEMPLATE.md`
4. `ADR_MIGRATION_CUTOVER_TEMPLATE.md`
5. `ADR_DEPRECATION_RETIREMENT_TEMPLATE.md`
6. `DECISION_LOG_TEMPLATE.md`

## How to Use in PRs

1. Add or update ADR before merging architecture-impacting changes.
2. Reference ADR in PR description under "Architecture Decision".
3. If behavior differs from ADR, update ADR in same PR.

## Suggested Review Cadence

- Review active ADRs once per sprint for migration/cutover items.
- Mark stale Proposed ADRs as Rejected or Superseded after 30 days.

