---
status: active
owner: project
updated: 2026-10-17
tags: [development, contributing]
---

# Contributing to Rokkad

Read [AGENTS.md](AGENTS.md), [agent memory](docs/AGENT_MEMORY.md) and
[Status](docs/STATUS.md) before changing the project. Use the existing Django
services, selectors and tests; preserve domain authority, immutable evidence and
Workspace isolation. Check the relevant ADR and domain guide first.

## Development and checks

Use Python 3.14 with pinned requirements and a disposable PostgreSQL database.
The [README](README.md#local-development), [container runbook](docs/implementation/container-and-ci.md)
and [testing guide](docs/implementation/testing-and-migrations.md) describe setup.
Keep owner-only migration credentials separate from restricted web/worker roles.
Never aim tests at normal development or production business data.

```sh
python scripts/check_current_docs.py --all-current
python scripts/check_repository_hygiene.py
python scripts/check_app_boundaries.py
python scripts/check_document_archives.py
python -m unittest scripts.test_repository_hygiene scripts.test_app_boundaries
node --test scripts/test_loan_directory.cjs scripts/test_counter_entry.cjs
python manage.py test <affected.test.module> --settings django_project.settings.test --noinput
```

Run relevant lifecycle, permission, accounting and RLS checks for behavioral
changes. CI runs on pull requests, main/rls-mvp and the maintained integration
branch `work/loan-servicing-contract-ld01`; manual dispatch remains available.
Do not move the remote default branch or remove release/checkpoint refs as cleanup.

VS Code automatic pytest/unittest discovery is disabled: use Django with explicit
test settings and isolated owner/runtime roles from its terminal. Do not run
competing suites against one test database.

## Files and documentation

Author static assets in `static/` or app-owned static directories. Generate
`staticfiles/` using collectstatic; never commit collected output, runtime media,
logs, local backups or test outputs. Put task logs under `.tmp/<dated-task>/` and
synthetic visual evidence under `outputs/<dated-task>/`. Keep secrets local.

Browser checks use [pinned offline fixtures](scripts/fixtures/bootstrap-5.3.8/README.md).
See [browser verification](docs/implementation/browser-layout-verification.md).
Original reference documents and sample PDFs are indexed in
[reference assets](docs/archive/reference/README.md).

Update Status after meaningful work; keep stable rules in memory, accepted
decisions in `docs/adr/`, flows in `docs/flows/`, implementation evidence in
`docs/implementation/`, and plans in `docs/plans/`. Archive dated execution history
with provenance and maintained links. Preserve customer-source, recovery and
untracked work; an ignored file is not necessarily disposable.

