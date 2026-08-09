---
status: accepted
owner: project
updated: 2026-08-07
tags: [adr, accounting, authorization, k7]
related:
  - ../plans/standalone-accounting-k7-production-boundary.md
  - ../constitution.md
---

# ADR: Standalone Accounting Production Authorization Policy

## Context

The persisted kernel accepts numeric actor IDs and caller-supplied timestamps.
That is suitable for domain proof but not a production trust boundary.

## Decision

1. Production callers use `accounting.facade`; direct mutation-service calls
   remain internal implementation boundaries.
2. Every facade action requires an authenticated, active user, an exact match
   between the current database schema and workspace, and an explicit workspace
   accounting permission.
3. Members may prepare vouchers and transactions. Admins and Owners may
   authorize, post, and reverse.
4. The server supplies authorization, posting, and reversal timestamps.
5. The authorizer cannot post the same voucher. This check reloads persisted
   authorization evidence so a stale caller object cannot bypass it.
6. A posting's original poster cannot approve its reversal. Reversal remains an
   append-only atomic correction performed by another elevated actor.
7. Superuser override still requires an explicit active tenant context.
8. Durable identity snapshots and created-by evidence remain K7.2 work; current
   actor IDs continue to reference shared users.

## K8 Owner-Operated Amendment

The owner accepted a simpler policy for small single-owner workspaces. Audited
preference `accounting__workflow_mode` has two modes:

- `OWNER` (default): only the persisted workspace Owner may use one explicit
  confirmation to create, authorize, and post. All three lifecycle states and
  immutable snapshots remain and truthfully name the same Owner. This is a
  deliberate segregation-of-duties waiver, not hidden impersonation.
- `TEAM`: the original K7 policy remains. Maker, authorizer, and poster actions
  are separate; the maker cannot authorize and the authorizer cannot post.

Owner confirmation is a dedicated facade operation requiring the matching
tenant, an authenticated active workspace Owner with posting permission, and
the separately audited activation gate. Ordinary authorize/post methods retain
their separation checks. Workflow-mode changes are audited configuration.

In `OWNER` mode, the same real Owner may also post an explicit reversal of
their own original transaction. It requires reversal date, reason, and typed
confirmation, retains the original posted voucher, and creates the exact
opposite immutable voucher. `TEAM` mode retains the different-user reversal
rule. An allocated credit-sale invoice cannot be reversed until its receipt
allocations are unwound by reversing the relevant receipts.

## Consequences

- Single-owner behavior is explicit production policy only in `OWNER` mode; it
  never selects or impersonates other users.
- Source adapters and future UI/API handlers must call the facade.
- K7.1 establishes authorization policy but does not expose a runtime route or
  make standalone accounting the production authority.
