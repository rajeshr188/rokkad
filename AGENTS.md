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

Rokkad is a SaaS mini ERP for small businesses where accounting is central. Business events become vouchers. Posted vouchers create immutable journal entries. Corrections happen through reversals.

Modules include accounting, loans, inventory, sales, purchase, commodity management, workspace management, subscription, authorization, onboarding, and customer portal.

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

- For tenant app model changes, use the `migrate_schemas` command from `django-tenants`.
- For shared app model changes, use `migrate_schemas --shared`.
- Do not rely on plain `migrate` for project migration guidance unless the task explicitly targets a non-tenant local check.

## What Not To Do

- Do not build disconnected modules.
- Do not create journal entries manually for every user action.
- Do not hide source-document relationships.
- Do not mutate posted accounting entries.
- Do not mix workspace/global data accidentally.
- Do not make inventory, commodity, and accounting inconsistent.
- Do not bypass DEA for ledger effects.

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
