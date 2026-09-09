---
status: active
owner: project
updated: 2026-06-17
tags: []
related: []
---

# Rokkad

Living project documentation now starts at [docs/README.md](docs/README.md).

Rokkad is a shared-schema Django SaaS application for operational pawn lending.
Its supported business apps are Party, Loans, Notify v2, and Rates. Every
business row has direct Workspace ownership, and PostgreSQL forced row-level
security isolates Workspaces under a restricted runtime database role.


## What This Project Includes

- Shared-schema multi-Workspace architecture with PostgreSQL forced RLS
- Workspace/company onboarding, membership, invitations, and subscriptions
- Explicit Workspace-scoped seeding
- Pawn-loan lifecycle, collateral custody, funding, documents, and evidence
- Party master data, Notify v2 delivery evidence, and Workspace Rates
- Invitation and membership flows (`django-invitations` + custom org models)
- Auth and social auth via `django-allauth`
- Workspace authorization through `WorkspaceAccess` and domain-service rules
- HTMX-enabled UI paths and dynamic preferences

## Tech Stack

- Python (project currently uses Django `6.0.3`)
- PostgreSQL using Django's standard backend plus forced RLS
- Django apps: orgs, onboarding, subscriptions, accounts, Party, Loans, Notify v2, Rates
- Frontend tooling: Django templates, HTMX, crispy forms, select2
- Infra/runtime: WhiteNoise, optional Redis via [cache configuration](docs/implementation/cache-configuration.md), Docker files, GitHub Actions CI smoke workflow

## Repository Highlights

- `apps/orgs`: Workspace, domains, memberships, roles, permissions, and invitations
- `apps/onboarding`: Workspace onboarding flow
- `apps/tenant_apps/*`: Workspace-owned Party, Loans, Notify v2, and Rates apps
- `apps/tenancy`: Workspace context, ownership registry, RLS operations, and checks
- `django_project/settings`: environment-based settings (`base`, `dev`)
- `django_project/docs`: architecture and operations documentation

## Quick Start (Local)

### 1) Clone and create virtual environment

```bash
git clone https://github.com/rajeshr188/rokkad.git
cd rokkad

python -m venv .venv
```

Windows PowerShell:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Configure environment variables

`manage.py` defaults to `django_project.settings.dev`, and settings are loaded from `.env`.

At minimum, define:

```env
DEBUG=True
SECRET_KEY=replace-me
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

DB_NAME=rokkad_shared_dev
DB_USER=postgres
DB_PASSWORD=owner-password
DB_RUNTIME_USER=rokkad_runtime
DB_RUNTIME_PASSWORD=runtime-password
DB_MIGRATION_USER=postgres
DB_MIGRATION_PASSWORD=owner-password
DB_MIGRATION_NAME=rokkad_shared_dev
DB_HOST=127.0.0.1
DB_PORT=5432

EMAIL_HOST=localhost
EMAIL_PORT=1025
EMAIL_USE_TLS=False
EMAIL_HOST_USER=test@example.com
EMAIL_HOST_PASSWORD=test
DEFAULT_FROM_EMAIL=test@example.com
ADMINS=Local Admin <admin@example.com>

GOOGLE_CLIENT_ID=

CLOUDFLARE_R2_BUCKET=dev-bucket
CLOUDFLARE_R2_ACCESS_KEY=dev-access-key
CLOUDFLARE_R2_SECRET_KEY=dev-secret-key
CLOUDFLARE_R2_BUCKET_ENDPOINT=http://localhost:9000
```

### 3) Prepare database

Create the PostgreSQL database and run ordinary Django migrations through the
owner-only settings module:

```bash
python manage.py migrate --settings django_project.settings.migration --noinput
```

Create superuser:

```bash
python manage.py createsuperuser
```

### 4) Seed baseline data

Public/shared defaults:

```bash
python manage.py seed_public_defaults
```

Workspace defaults for one Workspace:

```bash
python manage.py seed_workspace_defaults --workspace-id <workspace_id>
```

All Workspaces:

```bash
python manage.py seed_all_workspaces
```

### 5) Run the app

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000`.

## Workspace Provisioning And Seeding Flow

The project uses explicit, command-driven seeding rather than migration side effects.

At a high level:

1. Create the ordinary global Workspace during onboarding.
2. Run Workspace-scoped seed commands through `workspace_context`.
3. Validate expected canonical seed records through shared-schema checks.

Primary docs:

- `django_project/docs/TENANT_PROVISIONING_AND_SEEDING_GUIDE.md`
- `django_project/docs/TENANT_SEEDING_EXECUTION_RUNBOOK.md`

## Important Management Commands

- `python manage.py seed_public_defaults`
- `python manage.py seed_workspace_defaults --workspace-id <workspace_id>`
- `python manage.py seed_all_workspaces --dry-run`
- `python manage.py seed_all_workspaces --continue-on-error`
- Schema-parity checks are retired; shared-schema isolation is verified through Workspace/RLS gates.
- `python manage.py setup_permissions`

## Testing

Tests use Django's ordinary runner and the owner-backed test settings only to
create/drop the disposable shared-schema test database. Workspace isolation
tests explicitly assume a restricted `NOSUPERUSER NOBYPASSRLS` role for DML.

Example:

- `python manage.py test apps.tenant_apps.loans.tests --settings django_project.settings.test -v 2`

Seeing migration lines during tests is expected. The important isolation gate
is that all Workspace tables have forced RLS and no-context queries expose no
business rows.

## CI Smoke Validation

GitHub Actions workflow:

- `.github/workflows/tenant-seed-smoke.yml`

It runs:

- PR fast smoke: migrate + seed target tenant
- Push full smoke: migrate baseline + target, seed both, enforce parity

## Additional Documentation

- `apps/tenant_apps/girvi/docs/loan/interest_accrual_guide.md` â€” current Girvi interest accrual behavior, trigger paths, and future improvements
- `django_project/docs/INVITATION_FLOW_REFERENCE.md`
- `django_project/docs/ALLAUTH_HARDENING_PLAN.md`
- `django_project/docs/INVITATIONS_HARDENING_PLAN.md`
- `PERMISSION_MATRIX_GUIDE.md`
- `TROUBLESHOOTING_COMMON_GOTCHAS.md`

## Contributing

See `CONTRIBUTING.md`.

## License

MIT License. See `LICENSE`.

