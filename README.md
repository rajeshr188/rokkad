# Rokkad

Rokkad is a schema-per-tenant Django application for finance/inventory workflows, including Girvi (loan) flows, accounting (DEA), product/inventory, notifications, purchasing, and sales.

The project is built on `django-tenants`, with explicit tenant bootstrap and seeding commands for deterministic tenant provisioning.

## What This Project Includes

- Multi-tenant architecture with PostgreSQL schemas (`public` + per-tenant schemas)
- Workspace/company onboarding with optional template-schema cloning
- Explicit and idempotent seeding for public and tenant defaults
- Tenant parity validation command to detect seed drift
- Invitation and membership flows (`django-invitations` + custom org models)
- Auth and social auth via `django-allauth`
- Object-level permissions via `django-guardian`
- HTMX-enabled UI paths and dynamic preferences

## Tech Stack

- Python (project currently uses Django `6.0.3`)
- PostgreSQL (`django_tenants.postgresql_backend`)
- Django apps: orgs, onboarding, subscriptions, accounts, tenant domain apps
- Frontend tooling: Django templates, HTMX, crispy forms, select2
- Infra/runtime: WhiteNoise, Redis cache support, Docker files, GitHub Actions CI smoke workflow

## Repository Highlights

- `apps/orgs`: tenant model (`Company`), domains, memberships, roles, permissions, seed commands
- `apps/onboarding`: workspace onboarding and provisioning flow
- `apps/tenant_apps/*`: tenant-scoped business apps (`girvi`, `dea`, `product`, `rates`, `terms`, `notify`, etc.)
- `django_project/settings`: environment-based settings (`base`, `dev`)
- `django_project/docs`: architecture and operations documentation
- `.github/workflows/tenant-seed-smoke.yml`: CI smoke for tenant bootstrap + seeding parity

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

DB_NAME=dea-kiss-v2
DB_USER=postgres
DB_PASSWORD=postgres
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

Create PostgreSQL database and run shared migrations:

```bash
python manage.py migrate_schemas --shared --noinput
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

Tenant defaults for one schema:

```bash
python manage.py seed_tenant_defaults --schema <tenant_schema>
```

All tenant schemas:

```bash
python manage.py seed_all_tenants
```

### 5) Run the app

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000`.

## Tenant Provisioning And Seeding Flow

The project uses explicit, command-driven seeding rather than migration side effects.

At a high level:

1. Create/clone tenant schema during onboarding.
2. Run `seed_tenant_defaults` immediately after provisioning.
3. Validate expected canonical seed records via parity checks.

Primary docs:

- `django_project/docs/TENANT_PROVISIONING_AND_SEEDING_GUIDE.md`
- `django_project/docs/TENANT_SEEDING_EXECUTION_RUNBOOK.md`

## Important Management Commands

- `python manage.py seed_public_defaults`
- `python manage.py seed_tenant_defaults --schema <schema_name>`
- `python manage.py seed_all_tenants --dry-run`
- `python manage.py seed_all_tenants --continue-on-error`
- `python manage.py check_tenant_seed_parity --baseline-schema <schema_name> --fail-on-drift`
- `python manage.py setup_permissions`

## Testing (django-tenants)

`manage.py test` is configured with a tenant-aware test runner:

- `TEST_RUNNER = "django_project.test_runner.TenantAwareDiscoverRunner"`

This runner prepares test schemas using `migrate_schemas` semantics (schema-aware setup for `public` and tenant apps), rather than relying on plain non-tenant migration behavior.

Example:

- `python manage.py test apps.tenant_apps.girvi.tests -v 2`

Note: seeing migration lines during tests is expected. The important part is that migrations run in tenant schema context (for example, log lines prefixed with `[standard:public]`).

## CI Smoke Validation

GitHub Actions workflow:

- `.github/workflows/tenant-seed-smoke.yml`

It runs:

- PR fast smoke: migrate + seed target tenant
- Push full smoke: migrate baseline + target, seed both, enforce parity

## Additional Documentation

- `apps/tenant_apps/girvi/docs/loan/interest_accrual_guide.md` — current Girvi interest accrual behavior, trigger paths, and future improvements
- `django_project/docs/INVITATION_FLOW_REFERENCE.md`
- `django_project/docs/ALLAUTH_HARDENING_PLAN.md`
- `django_project/docs/INVITATIONS_HARDENING_PLAN.md`
- `PERMISSION_MATRIX_GUIDE.md`
- `TROUBLESHOOTING_COMMON_GOTCHAS.md`

## Contributing

See `CONTRIBUTING.md`.

## License

MIT License. See `LICENSE`.
