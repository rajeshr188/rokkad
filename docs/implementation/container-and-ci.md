---
status: active
owner: project
updated: 2026-09-09
tags: [deployment, docker, ci, rls]
related: [postgresql-runtime-role.md, ../plans/project-hardening.md]
---

# Containers and CI

The image uses Python 3.14 and a non-root application user. PostgreSQL 16 is the
development/CI baseline. The multi-stage build keeps compilers out of the runtime
image. `.dockerignore` allows only required application source, static assets and
startup/provisioning scripts; local environment files, uploads, dumps, Git history,
virtual environments and documentation are excluded. No credentials are build args.

## Local development, separate from the existing local database

Copy `.env.container.example` to `.env.container` and replace its three placeholders.
Use different passwords for owner and runtime. All commands below run from the repo
root and explicitly select that file; they do not use your normal development `.env`.

```sh
docker compose --env-file .env.container config --quiet
docker compose --env-file .env.container build
docker compose --env-file .env.container up -d db
# First initialization only: create a NEW runtime role and owner default grants.
docker compose --env-file .env.container run --rm migrate python scripts/provision_runtime_role.py
docker compose --env-file .env.container run --rm migrate
docker compose --env-file .env.container up -d web
```

Open http://localhost:8000. Stop any other server using that port first. Data is in
the `rokkad-dev` Compose project's named PostgreSQL/media volumes, not your existing
host database. PostgreSQL is not published on a host port. The database container's
owner is an administrator of this disposable development cluster; only the separate
runtime login enters the web service. Compose explicitly lists web environment
variables instead of loading owner secrets into it.

The provisioning script refuses an existing runtime role, rather than resetting its
password or extending its grants. Reuse the existing role for subsequent runs. Its
default table/sequence grants apply only to objects created by the same migration
owner. An existing external role/database should use the reviewed SQL in
[the role guide](postgresql-runtime-role.md), including default privileges for the
actual owner. Do not rerun provisioning as an unrelated database administrator and
assume future migrations by another owner inherit those grants.

For code updates: rebuild, run the migration service explicitly, then recreate web.
The web entry point runs deployment/database checks and rejects pending migrations;
it never applies migrations. Local `container_dev` settings allow HTTP cookies and
console email; they are separate from production and ordinary Windows dev settings.

Use `docker compose --env-file .env.container down` to stop this stack while retaining
data. Do not use `down --volumes` unless you intend to erase this development data.

## Production recipe

`docker-compose.production.yml` runs a versioned image against separately managed
PostgreSQL. It does not provision a database, publish private media, configure a TLS
proxy, activate billing or claim production acceptance.

Prepare private `.env.production.runtime` and `.env.production.migration` files using
your secret manager. These files are Git-ignored and excluded from the image.

- Runtime: explicit `DB_RUNTIME_USER`/`DB_RUNTIME_PASSWORD`; `DB_USER`/`DB_PASSWORD`
  must also contain the runtime identity because base settings read them. Include
  database host/port/name, a strong SECRET_KEY, exact DJANGO_ALLOWED_HOSTS, and the
  normal email/optional-provider settings required by settings. Do not include owner
  credentials. `DEBUG=False`; choose TLS/redirect configuration with your proxy.
- Migration: explicit `DB_MIGRATION_NAME`, `DB_MIGRATION_USER` and
  `DB_MIGRATION_PASSWORD`, plus base settings inputs. Never rely on the migration
  module's development database-name default for a production operation.
- The dormant Cloudflare configuration currently requires its four settings even
  when FileSystemStorage is used. Supply non-secret placeholders if it is unused;
  do not mistake those settings for an enabled private storage integration.

After backup/recovery and target-database checks, an operator can run:

```sh
# Export ROKKAD_IMAGE to a reviewed, explicitly versioned image tag first.
docker compose -f docker-compose.production.yml run --rm migrate
docker compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml up -d web
```

The image's default web command runs `scripts/start_web.py`, which enforces the
restricted-role and schema checks before Gunicorn. Non-container deployments should
use the same entry point (or run its checks as a mandatory release gate). Directly
invoking Gunicorn bypasses this launcher. Deploy checks currently fail on errors;
TLS/HSTS warnings require assessment for the actual proxy arrangement, not silent
dismissal. The proxy may serve static files but must not expose a broad `/media/`
alias. Complete [private-media acceptance](private-media-access.md) and restore
rehearsals before production.

## CI

`.github/workflows/workspace-checks.yml` runs on PRs, main/rls-mvp pushes and manual
dispatch. It provisions a new runtime role in a disposable PostgreSQL service,
migrates with owner-only settings, checks migration drift and verifies runtime
startup. A negative check proves owner startup fails specifically with tenancy.E020.
Explicit test labels cover context/metadata, deployment configuration, canonical
control-plane contracts, app authorization and the real first-loan HTTP journey;
Loans regressions use a separate fresh test DB run. RLS adversarial tests deliberately
use restricted roles; the test runner retains owner access for database lifecycle.

The workflow then builds (never publishes) the image and checks it against the
migrated database and collects production static assets with runtime credentials
only. CI credentials are disposable
constants, not deployment secrets. Dependency pins remain in requirements.txt;
the Docker build is a clean-install check, not an advisory/vulnerability audit.
