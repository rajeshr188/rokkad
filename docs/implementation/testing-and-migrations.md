---
status: active
owner: project
updated: 2026-09-09
tags: [implementation, testing, migrations]
---

# Testing and migrations

Use Python 3.14 and the current requirements. See [containers and CI](container-and-ci.md)
for reproducible startup, owner/runtime credentials and the disposable database
rehearsal. Historical instructions are [archived](../archive/context/2026-09-09/implementation/testing-and-migrations.md).

## Schema ownership

Run migrations only with the owner-only settings:

```powershell
python manage.py migrate --settings django_project.settings.migration
python manage.py makemigrations --settings django_project.settings.test --check --dry-run
```

Web and workers use the restricted runtime role. Never start them using migration
settings. New Workspace-owned tables need a direct non-null owner, forced RLS,
registry coverage and isolation tests. Existing billing control-plane tables have
their own explicit Workspace/actor boundaries; do not silently mix data planes.

## Relevant checks

```powershell
python manage.py check
python scripts/check_current_docs.py
python scripts/check_app_boundaries.py
python -m unittest scripts.test_app_boundaries
python manage.py test apps.subscriptions.tests apps.subscriptions.test_phase4_billing apps.subscriptions.test_checkout apps.subscriptions.test_recovery apps.subscriptions.test_reviews --settings django_project.settings.test --noinput
python manage.py test django_project.test_control_plane_contract_gate django_project.test_phase9_app_conformance_gate --settings django_project.settings.test --noinput
python manage.py test apps.tenant_apps.loans.tests --settings django_project.settings.test --noinput
```

Select affected modules for routine increments. Boundary/lifecycle changes need
meaningful permission, replay, rollback, immutable-evidence and isolation coverage.
Adversarial RLS DML must execute under a restricted role even though test-database
creation/migrations use the test owner. Fresh-process checks catch reliance on
ambient Workspace context. Use explicit test modules where package discovery would
resolve relative imports incorrectly.

Never run suites concurrently against the same test database. `--keepdb` is useful
for focused reruns, but retained TransactionTestCase/RLS state can affect broader
runs; use a clean disposable test database when necessary. Do not redirect tests
to normal development data. Never print database passwords or env-file contents.

Mock provider calls and mail in ordinary billing/notification checks. Razorpay setup
and external acceptance are shelved as [FW-002](../plans/future-work.md#fw-002-razorpay-setup-and-provider-test-mode-acceptance).
Physical media/print and deployment acceptance must not be inferred from unit tests.
Record commands, results and limits in [Status](../STATUS.md).
