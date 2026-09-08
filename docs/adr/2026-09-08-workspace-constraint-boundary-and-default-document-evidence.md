---
status: accepted
owner: project
updated: 2026-09-08
tags: [workspace, rls, loans, acceptance, documents]
related: [../architecture/control-plane-contracts.md, 2026-08-16-retire-accounting.md]
---

# Workspace constraint boundary and default document evidence

## Evidence

The first-loan HTTP acceptance journey under a restricted PostgreSQL role
reproduces a full-release failure at COMMIT: the deferred custody projection
trigger cannot see the collateral after `workspace_context()` restores the
previous database context. The same journey finds that default fixed-layout
tickets are regenerated on every GET when no custom layout is assigned.

## Decision

The outermost logical Workspace scope checks deferred constraints before
restoring its prior context. Reuse Django's `connection.check_constraints()`;
on PostgreSQL it checks immediately, then restores deferred mode. Same-Workspace
nested scopes leave checking to their outer scope so services can finish their
atomic workflow before projection guards execute. Failures roll back the scoped
unit. Work cannot leave pending constraint dependencies across Workspace scopes,
and callers must not depend on a custom constraint-timing mode surviving that
boundary. Global work sharing the transaction must also be constraint-valid at
the boundary. This preserves the existing ability to scope work inside a larger
transaction without leaving deferred RLS-dependent checks until context is gone.

Normal default-layout documents use the same immutable `LoanDocumentIssue`
ledger as custom layouts. Render the existing fixed layout once, record its
version and exact bytes, and reuse the official issue on subsequent requests.
Explicit administrator fixed-renderer recovery keeps its existing audited path.
No new document model, RLS policy, or schema migration is required.

## Verification

Use real transaction commits and a restricted role for the complete loan
journey, plus nested-scope rollback checks and existing context, document,
release, custody, and cross-app contract suites. Physical print and browser
camera acceptance remain operator checks.

See [README](../../README.md) for the project entry point.
