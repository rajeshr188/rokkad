---
status: active
owner: project
updated: 2026-09-09
tags: [loans, operations, workspace, rls]
related: [postgresql-runtime-role.md, action-permission-review.md, ../plans/project-hardening.md]
---

# Workspace-aware Loans operator commands

Run these commands with the restricted runtime database role and an explicit
Workspace ID. They establish and clear their own transaction-local RLS context;
neither a browser selection nor a saved user preference is used. Missing, invalid,
unknown or conflicting Workspace IDs are rejected. The historical `public` metadata
row is not a business Workspace.

These are trusted operator/scheduler entry points. They are not staff-facing APIs
and do not replace the action checks on public application services. Keep runtime
database credentials restricted to trusted operators. Do not expose shell commands
through an HTTP endpoint or infer Owner authority from their lack of a user argument.

## Seed draft products

```sh
python manage.py seed_default_loan_products --workspace-id 123
```

Requires an ACTIVE Workspace at entry. Creates the four default draft product
versions idempotently through the existing internal bootstrap helper. Does not
activate products or change saved loan terms. A failure rolls back the command's
database work. Web-triggered product seeding still uses its actor-authorized service.

## Inspect document evidence

```sh
python manage.py check_loan_document_integrity --workspace-id 123 --fail-on-findings
```

Read-only inspection uses the existing integrity selector. It can inspect suspended,
archived and deletion-pending Workspaces for recovery/support without enabling
business writes. Findings include their object references; the final count identifies
the Workspace. `--fail-on-findings` returns a nonzero exit after the context is closed.
This command does not repair, delete or republish evidence.

## Dispatch already-queued notices

```sh
python manage.py dispatch_pawn_loan_notices --workspace-id 123 --limit 100
```

This command can send real notifications: schedule/run it only when delivery is
intended. It requires an ACTIVE Workspace at entry and processes existing authorized
notice/job records; it does not create new notification intent or bypass staff
creation/retry permissions. A Workspace becoming inactive does not automatically
cancel an already-running delivery; schedule future invocations accordingly.

The default limit is 100 and the accepted range is 1–1000. Optional `--as-of` accepts
an ISO datetime; an explicit offset is recommended. Naive timestamps are interpreted
in the configured application timezone. Invalid calendar values are command errors.
Output reports due/sent/failed counts and Workspace ID. Existing per-notice failure
reporting is preserved: a completed batch with failed deliveries still reports its
counts; inspect these counts and saved delivery states rather than treating process
exit alone as proof that every notice was sent.

Prefer one bounded invocation per Workspace. Do not loop implicitly over all
Workspaces or retry already-completed deliveries outside the existing dispatch logic.
No notifications were sent while implementing/testing these command fixes.

In containers, pass the command to the runtime service, not the migration service:

```sh
docker compose --env-file .env.container run --rm web python manage.py check_loan_document_integrity --workspace-id 123 --fail-on-findings
```

The same app commands work with production settings and separately supplied runtime
credentials. Schema migrations continue to use the owner-only migration settings.

## Repeated monitoring refresh

`reassess_pawn_loans --workspace-id ID --batch-size 50 --repeat-seconds 300`
uses today's local date for each bounded pass and establishes its own Workspace
context. Use restricted runtime settings. An optional Compose monitoring service
runs this command through role/migration startup checks. The operator must select
and enable a Workspace job; this code change does not start it automatically.
See [setup, status meanings and failure handling](../flows/loan-health-monitoring.md).
