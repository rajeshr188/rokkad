---
status: superseded
owner: project
updated: 2026-08-12
tags: [loans, collateral, intake, numbering]
related: [2026-08-09-loans-collateral-identity-media-and-labels.md, ../domain/loans-collateral-intake.md]
---

# Collateral Intake Batch

> Superseded on 2026-08-12. The implementation was removed in favor of the
> smaller PawnLoan draft collateral split workflow. This ADR remains only as
> historical decision evidence. Retired tables are preserved outside current
> Django model state so removal does not destroy already-captured data.

## Context

Operators commonly capture many items for one Party before deciding whether
they form one or several PawnLoan contracts. Creating a PawnLoan first consumes
an official series number before that grouping decision is known.

## Decision

`CollateralIntakeBatch` is tenant-scoped pre-contract working data. Members may
capture mutable items and photographs and arrange arbitrary loan groups. Every
group independently selects Series, product, date, tenure, and allocations.

Owner/Admin conversion validates every group from one fingerprinted preview and
creates all PawnLoan drafts in one transaction. Conversion is the boundary that
allocates permanent numbers, transfers media into immutable PawnLoan evidence,
and freezes the intake. No partial conversion, accounting, approval, custody,
official document, or number reuse is permitted.

Abandonment retains the intake header, counts, actor, time, and reason but
removes pre-contract items and working media.

## Consequences

- Intake references are operational identities, not regulatory loan numbers.
- Failed conversion rolls back every draft and sequence advance.
- Converted and abandoned intake evidence is read-only.
- Direct PawnLoan draft creation remains available for simple origination.
