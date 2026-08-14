---
status: proposed
owner: loans
updated: 2026-08-11
tags: [decision-brief, loans, architecture]
related: [../architecture-plan.md]
---

# ADR-005: Keep Risk Inside Loans

## Status

Proposed decision brief.

## Context

Risk depends closely on PawnLoan contracts, immutable loan events, accrual,
collateral custody, renewal, release, notices, and tenant migrations. A new
Django app would add registration and dependency complexity before a separate
bounded context is proven.

## Proposed decision

Implement exposure, obligations, valuation boundaries, risk assessment,
snapshots, events, and selectors within the existing `loans` app. Preserve
domain/service/selector boundaries inside that app. Reconsider extraction only
when several loan aggregates share a stable, independent risk API.

## Consequences

The first implementation follows existing tenant and migration conventions and
avoids a circular integration layer. Internal modules must still remain small
and must not move business calculations into models, views, or templates.
