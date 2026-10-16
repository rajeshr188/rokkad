---
status: active
owner: project
updated: 2026-10-17
tags: [dependencies, development, ci, security]
---

# Python dependency and tooling audit

## Independent integration review (17 October)

The owner confirmed the source session is finished and authorized review and
integration. A frozen 24-file snapshot over `693031a7` is reviewed in a separate
worktree, preserving the original pending files. Direct/installed pins, pip
consistency, Ruff and changed-file Black pass. Full current documentation links,
22 preserved document originals, repository guards and seven guard tests pass.
All 18 shell/credential tests pass independently. AST comparison confirms the
Notify service/test formatting has no behavior changes outside the canonical
Workspace credential lookup. Earlier 355-case consumer evidence and its separate
18-case fixture rerun retain their documented limits; this review does not sum
overlapping selections or claim fresh full Linux acceptance.

The development workflow remains a proposed guide. No GitHub default/protection
setting, remote branch, production deployment or data-repair permission changes
follow from integrating this dependency/tooling change. Exact-revision Linux CI
must pass before release acceptance. Review manifests/results remain ignored
under `.tmp/dependency-review-20261017/`.

The owner requested an installed-package usage/update review, synchronized
requirements and an assessment of uv, Black and other linters. This is local
source/environment work. The verified [production release](counter-release-20261016.md)
remains unchanged. [Machine-readable evidence](python-dependency-audit-20261017.inventory.json)
preserves each initial package/version, static import paths and observed PyPI versions.

## What is actually used

The initial `.venv314` has Python 3.14.3 and **84 distributions**, with `pip check`
passing. Imports/literal references were inspected across **1,447 tracked Python
files**, including migrations/tests. Django app registration, template tags,
backends, commands and dynamic export formats were reviewed separately: missing
first-party imports alone do not establish that a package is unused.

The previous files contain **67 explicit requirements and 71 constraints**.
The revised `requirements.txt` has **41 direct runtime dependencies** and the
uv-generated universal Python 3.14 `requirements.lock` resolves **65 distributions**.
Botocore and urllib3 are explicit because active storage/media code imports them;
local botocore 1.43.98 must align with the existing runtime constraint 1.43.100.
Transitive requirements belong in the lock, rather than the direct list.

Twelve initial packages are unused/retired: **django-activity-stream,
django-dynamic-preferences, django-extensions, django-guardian,
django-slick-reporting, django-viewflow, persisting-theory, async-timeout,
MarkupPy, pytz, qrcode and simplejson**. Six disappear from the old runtime
constraint set: async-timeout (Redis only requires it before Python 3.11.3),
MarkupPy (current Tablib HTML uses the standard library), pytz/simplejson
(former slick-reporting dependencies), qrcode (active QR documents use ReportLab)
and setuptools (build/environment tooling). Retained legacy preference tables
use local compatibility models; dynamic-preferences is not re-enabled.
Historical migrations and permission aliases are unchanged. Colorama, setuptools
and wheel are environment/tooling remnants, distinct from business dependencies.

| Retained dependency | Current use |
| --- | --- |
| allauth, invitations | Password/Google authentication and team invitations |
| crispy forms/Bootstrap, widget-tweaks | Registered Django/template/form rendering |
| cleanup, colorfield | Active models/signals and historical migrations |
| filter/tables2, select2, HTMX, render-block | Loan/Party browsing, borrower search and partial rendering |
| django-mptt | Registered in base settings, but no first-party tree model import found; separate registration/template review required before removal |
| django-redis/redis | Optional supported cache backend; default local-memory cache does not justify removal |
| storages, boto3/botocore | Private R2 storage/cleanup, platform SES and backup tooling |
| urllib3 | Legacy-media reader exceptions and HTTP dependencies |
| tablib XLS/XLSX/ODS extras | Preserve current dynamic format availability, including XLS/HTML exports; pandas/YAML are not added |
| openpyxl, defusedxml | Spreadsheet portability and safe XML parsing |
| ReportLab, PyMuPDF, Pillow | Loan/invoice documents, image/overlay previews and QR rendering |
| phonenumber-field/phonenumbers | Party and platform WhatsApp phone validation |
| dateutil, num2words | Subscription/loan dates and document words |
| py-moneyed/Babel/typing-extensions | Transitive django-money dependencies |
| PyJWT/cryptography | Google-provider verification and encrypted Workspace WhatsApp credentials |
| gunicorn/WhiteNoise, psycopg2 | Runtime server/static assets and PostgreSQL |
| tzdata | Cross-platform ZoneInfo fallback, required on Windows |
| Playwright/greenlet/pyee | Optional browser acceptance tooling, outside the runtime image |

## Updates applied and available

Official [PyPI JSON metadata](https://docs.pypi.org/api/json/) was queried using
package names only. Latest observed versions below are an October 17 snapshot,
not an automatic compatibility recommendation.

| Applied dependency | Before | After | Evidence |
| --- | --- | --- | --- |
| Django | 6.1.1 | 6.1.2 | Security/bugfix patch: [release notes](https://docs.djangoproject.com/en/6.1/releases/6.1.2/) |
| cryptography | 50.0.1 | 50.0.2 | OpenSSL wheel refresh: [changelog](https://cryptography.io/en/latest/changelog/) |
| PyJWT | 2.15.0 | 2.15.1 | Correctly padded JWS compatibility patch: [changelog](https://pyjwt.readthedocs.io/en/stable/changelog.html) |
| certifi | 2024.7.4 | 2026.7.22 | Current CA bundle: [PyPI](https://pypi.org/project/certifi/) |
| tzdata | 2024.1 | 2026.5 | Current timezone data: [PyPI](https://pypi.org/project/tzdata/) |

Major updates are held: Redis 5 to 8, django-redis 5 to 7, debug-toolbar 4 to 8,
tables2 2 to 3, Pillow 12 to 13, ReportLab 4 to 5 and Gunicorn 23 to 26.
Other available updates should be tested in groups by their consumers:
authentication, forms/search, media/mail, document rendering, export/import and
cache behavior. Metadata/Python compatibility alone does not establish app
compatibility. Playwright remains at 1.62.0 with its existing greenlet/pyee pins;
a browser upgrade changes the browser acceptance baseline.

## Tool usage before and after

| Tool | Before | Implemented |
| --- | --- | --- |
| uv | Global Python 3.11 uv 0.6.14; no repo invocation | Pinned project-local 0.13.1, universal compilation and explicit environment install/sync |
| Black | Global 23.7.0; no config/CI use | Pinned 26.10.1, Python 3.14/88 columns, changed-file CI check |
| Ruff | No project installation/configuration | Pinned 0.17.1; E9/F63/F7/F82 correctness checks across maintained source |
| pip-audit | Previous dated release scan, no maintained dev dependency | Pinned 2.10.1 outside runtime; explicit current advisory scan |
| isort/flake8/pylint | No configured use found | Not added; avoid overlapping style tools in this initial gate |
| mypy | No configured use found | Not added; mypy-extensions is a Black dependency, not type checking |
| pre-commit | No configured hooks found | Local commands and CI; no automatic Git hooks installed |
| Existing guards/tests | Install consistency, docs/hygiene, app boundaries and RLS/domain tests in CI | Preserved, with direct-pin and installed-runtime drift checks in every suite |

The initial Black check reports **1,091 files to reformat and 164 already formatted**.
CI checks changed/new maintained Python files, avoiding a forced whole-repository
rewrite. Ruff covers maintained application/infrastructure/scripts roots.
Historical migrations, docs/prototypes and generated files are excluded. Broader
unused-import/style/type rules remain future work. VS Code defaults to `.venv314`;
activate the environment/use `python -m black` to avoid old global executables.

Ruff found an active WhatsApp credential helper referencing undefined legacy
`connection.tenant`. It now uses canonical `current_workspace_id()`; absent context
returns empty configuration without querying credentials. Two undefined names occur
only in existing uncollected `_retired_*` test helpers; narrow line-level F821 comments
identify those references without importing retired APIs or ignoring whole files.
The two touched Notify files are Black-formatted. Their AST is verified identical
apart from the reviewed canonical-context correction.

## Commands and dependency ownership

`requirements.txt` remains the direct runtime input; `requirements.lock` is its full
resolved constraint set. `requirements-dev.txt`/`requirements-dev.lock` are separate,
with shared runtime versions constrained during tool resolution. Docker's allowlist
excludes development requirements, tool configuration and audit evidence.
`pyproject.toml` is tool configuration only; this is not a migration to `uv sync`
project groups. [uv supports requirement compilation/sync directly](https://docs.astral.sh/uv/pip/compile/).

```sh
python -m pip install -r requirements.txt -c requirements.lock
python -m pip install -r requirements-dev.txt -c requirements-dev.lock
# Optional acceptance tooling:
python -m pip install -r requirements-browser.txt -c requirements-browser.lock
python scripts/check_dependencies.py --installed
python scripts/check_python_quality.py
python scripts/check_python_quality.py --base <base-commit>
python -m black <changed-python-files>

# Preserve other reviewed versions when regenerating:
uv pip compile requirements.txt --constraint requirements.lock --universal --python-version 3.14 --output-file requirements.lock
uv pip compile requirements-dev.txt --constraint requirements.lock --universal --python-version 3.14 --output-file requirements-dev.lock
uv pip compile requirements-browser.txt --constraint requirements.lock --universal --python-version 3.14 --output-file requirements-browser.lock
# Edit the selected exact direct/constraint pins first; never silently --upgrade all.

# Runtime-only NEW environment:
uv pip sync --python <new-env-python> requirements.lock
uv pip check --python <new-env-python>
# Sync removes extras. A developer env needs a combined runtime/dev/browser resolution.
python -m pip_audit --disable-pip --no-deps -r requirements.lock
```

The independent quality CI job has no database and uses full Git history for its
comparison base. Each runtime suite still installs with pip/runtime constraints,
checks `pip check` and installed pins, then runs existing schema/RLS tests.
Development packages do not enter application images. Global Python 3.11 tools
remain untouched.

## Validation and boundaries

Clean isolated Windows/Python 3.14 runtime installation resolves 65 packages.
The installed-pin checker, uv compatibility check, Django system checks, Ruff
and changed-file Black pass. Two negative guard probes reject direct-pin mismatch
and installed-version drift. Seven existing boundary/hygiene guard tests pass.
The runtime advisory result is **65 packages, zero skipped, no known vulnerabilities**;
this is a dated package scan, not an application/OS security assessment.
The initial focused run passed 353 of 355 tests in 312.244 seconds; two rendering
fixtures lacked sessions. Both reproduced under the original Django 6.1.1 baseline.
Shell fixtures now provide a session and isolate the database-backed account-journey
service (covered by separate passing onboarding tests). The complete shell/credential
rerun passed 18 tests. Test production logic is unchanged by that fixture repair.

The main `.venv314` was reconciled to **96 runtime/development/browser distributions**:
twelve unused/retired packages and three environment remnants were removed, the
reviewed runtime pins were applied and pinned tools installed. Playwright 1.62.0,
greenlet 3.5.5 and pyee 13.0.1 are preserved in `requirements-browser.lock`.
Both pip/uv compatibility checks, installed runtime pins and local quality checks
pass. Original exact version restore pins and the combined local resolution remain
under the dated task directory. Existing server processes need a restart to load
the installed library updates; no running production process was changed.

No application-image build, full six-group CI run or production deployment/rehearsal
is performed. Universal Linux resolution still needs normal clean-image/CI/release
gates before promotion. Test data stays in a uniquely named disposable local
PostgreSQL database; provider calls are mocked. Logs, original environment restore
pins and sync preview are retained in `.tmp/dependency-audit-20261017/`.
The disposable test database and both task-created temporary environments were
removed after verification. The reconciled `.venv314` and audit evidence remain.
The inventory contains package/version and source-path evidence, with no customer
records or credentials.

## Installed inventory before reconciliation

Each official PyPI endpoint is included in the JSON evidence. Static imports and
strings are bounded evidence rather than complete dynamic reachability.

| Package | Installed before | Runtime pin | Latest observed | Classification |
| --- | --- | --- | --- | --- |
| asgiref | 3.9.1 | 3.9.1 | 3.12.1 | Transitive runtime |
| async-timeout | 4.0.3 | — | 5.0.1 | Unused/retired |
| babel | 2.16.0 | 2.16.0 | 2.18.0 | Transitive runtime |
| boto3 | 1.43.98 | 1.43.98 | 1.43.114 | Direct runtime |
| botocore | 1.43.98 | 1.43.100 | 1.43.114 | Direct runtime |
| certifi | 2024.7.4 | 2026.7.22 | 2026.7.22 | Transitive runtime |
| cffi | 2.0.0 | 2.0.0 | 2.1.1 | Transitive runtime |
| chardet | 5.2.0 | 5.2.0 | 7.6.0 | Transitive runtime |
| charset-normalizer | 3.3.2 | 3.3.2 | 3.5.2 | Transitive runtime |
| colorama | 0.4.6 | — | 0.4.6 | Environment/tooling |
| crispy-bootstrap5 | 2024.2 | 2024.2 | 2026.9 | Direct runtime |
| cryptography | 50.0.1 | 50.0.2 | 50.0.2 | Direct runtime |
| defusedxml | 0.7.1 | 0.7.1 | 0.7.1 | Direct runtime |
| diff-match-patch | 20241021 | 20241021 | 20241021 | Transitive runtime |
| Django | 6.1.1 | 6.1.2 | 6.1.2 | Direct runtime |
| django-activity-stream | 2.0.0 | — | 2.0.0 | Unused/retired |
| django-allauth | 65.19.4 | 65.19.4 | 65.20.0 | Direct runtime |
| django-appconf | 1.0.6 | 1.0.6 | 1.2.0 | Transitive runtime |
| django-cleanup | 8.1.0 | 8.1.0 | 9.0.0 | Direct runtime |
| django-colorfield | 0.11.0 | 0.11.0 | 0.14.0 | Direct runtime |
| django-crispy-forms | 2.3 | 2.3 | 2.7 | Direct runtime |
| django-debug-toolbar | 4.4.6 | 4.4.6 | 8.0.0 | Direct runtime |
| django-dynamic-preferences | 1.16.0 | — | 1.17.0 | Unused/retired |
| django-environ | 0.11.2 | 0.11.2 | 0.14.0 | Direct runtime |
| django-extensions | 3.2.3 | — | 4.1 | Unused/retired |
| django-filter | 24.3 | 24.3 | 26.2 | Direct runtime |
| django-guardian | 2.4.0 | — | 3.5.1 | Unused/retired |
| django-htmx | 1.19.0 | 1.19.0 | 1.29.0 | Direct runtime |
| django-import-export | 4.4.1 | 4.4.1 | 4.4.2 | Direct runtime |
| django-invitations | 2.1.0 | 2.1.0 | 2.1.0 | Direct runtime |
| django-js-asset | 2.2.0 | 2.2.0 | 4.2.0 | Transitive runtime |
| django-money | 3.6.0 | 3.6.0 | 3.6.2 | Direct runtime |
| django-mptt | 0.16.0 | 0.16.0 | 0.19.1 | Direct runtime |
| django-phonenumber-field | 8.0.0 | 8.0.0 | 8.5.0 | Direct runtime |
| django-redis | 5.4.0 | 5.4.0 | 7.0.0 | Direct runtime |
| django-render-block | 0.10 | 0.10 | 0.11 | Direct runtime |
| django-select2 | 8.4.8 | 8.4.8 | 8.6.1 | Direct runtime |
| django-slick-reporting | 1.3.1 | — | 1.5.0 | Unused/retired |
| django-storages | 1.14.6 | 1.14.6 | 1.14.6 | Direct runtime |
| django-tables2 | 2.7.0 | 2.7.0 | 3.0.1 | Direct runtime |
| django-viewflow | 2.2.15 | — | 2.4.0 | Unused/retired |
| django-widget-tweaks | 1.5.0 | 1.5.0 | 1.5.1 | Direct runtime |
| docopt | 0.6.2 | 0.6.2 | 0.6.2 | Transitive runtime |
| et-xmlfile | 1.1.0 | 1.1.0 | 2.0.0 | Transitive runtime |
| greenlet | 3.5.5 | — | 3.5.6 | Optional browser |
| gunicorn | 23.0.0 | 23.0.0 | 26.2.0 | Direct runtime |
| idna | 3.20 | 3.20 | 3.20 | Transitive runtime |
| jmespath | 1.1.0 | 1.1.0 | 1.1.0 | Transitive runtime |
| MarkupPy | 1.14 | — | 1.18 | Unused/retired |
| num2words | 0.5.13 | 0.5.13 | 0.5.14 | Direct runtime |
| odfpy | 1.4.1 | 1.4.1 | 1.4.1 | Transitive runtime |
| openpyxl | 3.1.5 | 3.1.5 | 3.1.5 | Direct runtime |
| packaging | 24.1 | 24.1 | 26.3 | Transitive runtime |
| persisting-theory | 1.0 | — | 1.0 | Unused/retired |
| phonenumbers | 8.13.43 | 8.13.43 | 9.0.41 | Direct runtime |
| pillow | 12.3.0 | 12.3.0 | 13.0.0 | Direct runtime |
| pip | 26.2.1 | — | 26.2.1 | Environment/tooling |
| playwright | 1.62.0 | — | 1.64.0 | Optional browser |
| psycopg2 | 2.9.11 | 2.9.11 | 2.9.13 | Direct runtime |
| py-moneyed | 3.0 | 3.0 | 3.0 | Transitive runtime |
| pycparser | 2.22 | 2.22 | 3.11 | Transitive runtime |
| pyee | 13.0.1 | — | 14.0.0 | Optional browser |
| PyJWT | 2.15.0 | 2.15.1 | 2.15.1 | Direct runtime |
| PyMuPDF | 1.27.2 | 1.27.2 | 1.28.2 | Direct runtime |
| python-dateutil | 2.9.0.post0 | 2.9.0.post0 | 2.9.0.post0 | Direct runtime |
| pytz | 2024.1 | — | 2026.5 | Unused/retired |
| qrcode | 8.2 | — | 8.2 | Unused/retired |
| razorpay | 2.0.1 | 2.0.1 | 2.0.1 | Direct runtime |
| redis | 5.0.8 | 5.0.8 | 8.1.0 | Transitive runtime |
| reportlab | 4.2.2 | 4.2.2 | 5.0.1 | Direct runtime |
| requests | 2.34.2 | 2.34.2 | 2.34.2 | Direct runtime |
| s3transfer | 0.19.2 | 0.19.2 | 0.19.2 | Transitive runtime |
| setuptools | 82.0.1 | — | 84.0.0 | Environment/tooling |
| simplejson | 3.19.3 | — | 4.2.0 | Unused/retired |
| six | 1.16.0 | 1.16.0 | 1.17.0 | Transitive runtime |
| sqlparse | 0.6.0 | 0.6.0 | 0.6.0 | Transitive runtime |
| tablib | 3.10.0 | 3.10.0 | 3.10.0 | Direct runtime |
| typing_extensions | 4.12.2 | 4.12.2 | 4.16.0 | Transitive runtime |
| tzdata | 2024.1 | 2026.5 | 2026.5 | Direct runtime |
| urllib3 | 2.8.0 | 2.8.0 | 2.8.0 | Direct runtime |
| wheel | 0.46.3 | — | 0.48.0 | Environment/tooling |
| whitenoise | 6.7.0 | 6.7.0 | 6.12.0 | Direct runtime |
| xlrd | 2.0.1 | 2.0.1 | 2.0.2 | Transitive runtime |
| xlwt | 1.3.0 | 1.3.0 | 1.3.0 | Transitive runtime |
