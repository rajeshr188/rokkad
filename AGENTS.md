---
status: active
owner: project
updated: 2026-06-17
tags: [agents, codex, copilot]
related: [docs/AGENT_MEMORY.md, docs/STATUS.md, docs/constitution.md, docs/adr/, docs/domain/]
---

# AGENTS.md

This file is the operating contract for Codex, Copilot, and other AI coding agents working in this repository.

## Required Reading Order

1. Always read [docs/AGENT_MEMORY.md](docs/AGENT_MEMORY.md) first.
2. Always read [docs/STATUS.md](docs/STATUS.md) before planning work.
3. Check [docs/adr/](docs/adr/) before changing architecture.
4. Check [docs/domain/](docs/domain/) before changing business logic.
5. Check [docs/constitution.md](docs/constitution.md) when a change touches accounting, posting, reversals, or tenant isolation.

## Project Summary

Rokkad is a shared-schema SaaS pawn-lending application. Its supported business
apps are Party, Loans, Notify v2, and Rates. PostgreSQL forced RLS isolates
Workspace-owned rows under a restricted runtime role.

## Documentation Rules

1. Update [docs/STATUS.md](docs/STATUS.md) after meaningful changes.
2. Add new ADRs when making important architecture decisions.
3. Do not create random markdown files in the project root.
4. Put documentation in the correct `docs/` folder:
   - Architecture decisions: `docs/adr/`
   - Business/domain explanations: `docs/domain/`
   - User and system flows: `docs/flows/`
   - Implementation notes: `docs/implementation/`
   - Current/future/completed work: `docs/plans/`
   - Superseded or historical docs: `docs/archive/`

## Coding Rules

Rokkad follows the KISS principle: prefer the simplest design that correctly
enforces the domain rules. Reuse ordinary Django and existing project patterns;
do not introduce frameworks, indirection, abstraction layers, or configurability
without a concrete current need. Simplicity must not bypass accounting,
immutability, authorization, audit, or tenant-isolation requirements.

Before implementing meaningful work:

1. Inspect existing models, URLs, views, templates, services, and tests.
2. Propose or choose the smallest coherent change.
3. Keep accounting logic out of templates.
4. Keep posting logic out of views.
5. Prefer services, commands, facades, and selectors for business workflows and cross-app behavior.
6. Add or update tests for posting rules, lifecycle transitions, accounting effects, and boundary changes.

## Migration Rules

- Use ordinary Django migrations through the owner-only settings module:
  `python manage.py migrate --settings django_project.settings.migration`.
- Web and worker processes must use the restricted runtime database role.
- Tests use `--settings django_project.settings.test`; adversarial RLS DML must
  execute under a restricted role.
- New Workspace-owned tables require direct non-null ownership, forced RLS,
  registry coverage, and isolation tests.

## What Not To Do

- Do not build disconnected modules.
- Do not create journal entries manually for every user action.
- Do not hide source-document relationships.
- Do not mutate posted accounting entries.
- Do not mix workspace/global data accidentally.
- Do not make inventory, commodity, and accounting inconsistent.
- Do not reintroduce retired accounting, DEA, Girvi, Product, Contact, or legacy
  Notify dependencies.

## Documentation Steward Responsibilities

Whenever meaningful work is performed:

- `docs/STATUS.md` tracks current progress and risks.
- `docs/AGENT_MEMORY.md` tracks stable project understanding.
- `docs/adr/` tracks important decisions.
- `docs/domain/` tracks business knowledge.
- `docs/flows/` tracks user and system journeys.
- `docs/implementation/` tracks technical details.
- `docs/plans/` tracks active, future, and completed work.

Documentation must evolve with code. Never leave documentation stale.
