---
status: archived
owner: project
updated: 2026-06-17
tags: [implementation, dependencies, architecture]
related: [../domain/accounting.md, ../domain/girvi.md, ../adr/]
---

> Historical snapshot from docs/implementation/dependency-policy.md before the 2026-09-09 documentation cleanup.
> Old priorities and architecture statements are preserved as evidence, not current instructions.
> Use [current documentation](../../../../README.md) first.


# Dependency Policy

## Direction

- DEA is the accounting core and should expose stable public APIs through its facade.
- Girvi exposes cross-app reads through its facade/selectors.
- Contact owns party profile data and should not import Girvi internals for loan summaries.
- Domain apps may depend on shared infrastructure, but app-to-app dependencies should be intentional and tested.
- Posting internals, models, and seed details should not leak to other apps when a facade exists.

## Enforcement

- Architecture import tests should protect approved boundaries.
- New cross-app reads should start as selectors/facade methods.
- New cross-app writes should start as command/use-case services.

Source matrix is archived at [DEPENDENCY_POLICY_MATRIX](../../../old-docs/DEPENDENCY_POLICY_MATRIX.md).
