---
status: active
owner: project
updated: 2026-09-24
tags: [release, cutover, readiness, security]
related: [linode-production-cutover.md, container-and-ci.md, ../STATUS.md]
---

# Consolidated production release candidate, September 24

## Decision and scope

The owner authorized consolidating the accumulated rehearsal changes, building one
versioned image, verifying fresh/upgrade migrations and identifying release blockers.
This does not authorize production cutover. Assembly is on the local branch
`release/2026-09-24-rc1`; no repository push or production routing change is included.

The candidate incorporates preference-library retirement with retained legacy data,
navigation and loan workflow discoverability, number/date previews, borrower filters,
paged and analytical reports, rupee ticket formatting, automatic draft products,
subscription continuity and the bound JCL/JSK template installer. Accepted template
packs remain private configuration and must be installed against the actual target;
they are not customer data embedded in the image.

## Build and source controls

- Build the ordinary multi-stage Dockerfile from committed application source,
  rather than layering another patch onto the rehearsal image.
- Pin the Python base-image digest and all resolved runtime distributions through
  `requirements.lock`. This captures the current dependency baseline; it does not
  assert that the baseline is secure. OS package repositories remain external build
  inputs; retain the resulting image digest for exact deployment/rollback identity.
- Set `ROKKAD_REVISION` at build time; it is recorded in the OCI revision label.
- Package only the build-input allowlist from the source commit. `.dockerignore`
  excludes secrets, uploads, backups and local artifacts. The template installer
  is now explicitly included. Scratch/output/worktree directories are Git-ignored.
- An existing tracked SQL backup was removed from this branch's index, leaving its
  local file intact. Historical Git objects were not rewritten. Do not distribute
  full repository history as a deployment artifact.
- CI includes the new subscription-access, automatic-product and preference-retention
  checks and installs with the same dependency constraints as the container build.

## Security gate: blocked

A corrected `pip-audit` scan of the rehearsal runtime's package **names and versions**
checked 72 distributions with zero skips and reported advisories for 11 packages.

The same scan was repeated against the final clean-built candidate image, without
deployment credentials or customer-data mounts: 72 checked, zero skipped, the same
11 flagged dependencies. Final-image evidence is in `evidence/candidate-audit/`.

| Dependency | Candidate baseline |
| --- | --- |
| Django | 6.0.3 |
| django-allauth | 64.1.0 |
| django-select2 | 8.2.1 |
| cryptography | 43.0.0 |
| PyJWT | 2.9.0 |
| Pillow | 12.1.1 |
| requests | 2.32.3 |
| urllib3 | 2.2.2 |
| idna | 3.7 |
| sqlparse | 0.5.1 |
| tablib | 3.5.0 |

These are scanner findings, not proof that every advisory is exploitable in Rokkad.
Do not count duplicate advisory entries as distinct defects. At least one PyJWT
finding has no scanner-provided fix version, so version bumps alone cannot be
declared sufficient without reviewing that advisory's applicability.

The first attempted scan used `pip freeze` output containing local wheel URLs and
did not establish advisory coverage; it was corrected rather than accepted as a
clean result. Raw and summarized corrected evidence is retained under the host's
`release-candidate-20260924/evidence/` directory. The summary contains only public
package versions/advisory IDs and is also retained in ignored local outputs.

Before production promotion: review the advisories, select supported fixes, update
direct pins and constraints together, rebuild, rerun authentication/upload/import/
document/storage and financial/RLS regressions, and repeat the advisory scan.
Keep payment-provider calls mocked until the separately approved acceptance work.

## Validation

The initial consolidated source is `ec96cce6`. Its ordinary Docker build succeeded.
Owner-only migrations and migration-drift checks passed on an empty database and
a restored pre-preference-retirement rehearsal backup. Ordered row fingerprints
preserved all 99 existing Party/Loans/subscription tables and five preference/audit
tables; synthetic nonempty legacy preferences were included in the disposable copy.
The fresh database has empty retained preference tables without installing the
retired package or recording its package migrations.

The first 201-module run executed 1,906 tests and exposed stale shell/navigation,
historical-document and extracted-view assertions, missing commercial-access test
fixtures, and two tests attempting to reverse later irreversible audit migrations.
Those checks have been aligned with the accepted behavior. The two migration tests
exercise the original forward SQL data operations without undoing later evidence
protections; they do not claim to migrate a historical schema backward. The full
fresh/restored forward migration checks are separate release evidence.

Final source/image identity:

- Source: `520c8ecb`, on `release/2026-09-24-rc1`.
- Image: `rokkad:rc-20260924-520c8ecb`.
- Local Docker image ID: `sha256:e4942264d0300fe9395cab8eb864fa6a65a3e6f7cfbfe929f869fca3737e5f9c`.
- Allowlisted source archive SHA-256:
  `ad0f781fee1e0e0711e0304fd85fc6a4f43c703331d7a30424ebcd07ddda8a52`.

The final image passed startup/schema checks as `rokkad_runtime`, with neither
superuser nor RLS bypass. Non-root UID 10001 startup and `collectstatic` passed in a
separate candidate static volume. Owner-role startup was rejected specifically with
`tenancy.E020`. `pip check` and packaged ticket-installer `--help` passed. The final
checkpoint changes test fixtures/assertions only; migration files are unchanged from
the initial clean-built migration candidate.

On both fresh and restored databases, both customer-creation paths prepared exactly
four DRAFT products, with idempotent retries, explicit RLS context and transactional
rollback on preparation failure. On the restored copy, all three Workspaces passed
owner/staff read pages, denied writes, grace/expiry, extension/revocation, lifecycle,
RBAC and immutable-access-evidence checks. Existing JCL and JSK saved PDFs matched
their checksums; Lakshmi had no saved issued PDF for that check. Synthetic access
changes were rolled back, no financial writes/provider calls occurred, and all 104
pre-existing table fingerprints remained unchanged after the probes.

The isolated harness initially omitted fresh-database runtime grants and collected
static assets. It was corrected to use the existing role-provisioning script and a
separate static volume. Neither omission required an application-policy change.
Deployment checks retain the HSTS warning (`security.W004`); choose the production
HTTPS/HSTS policy as part of the actual proxy configuration review.

The final full regression run passed **1,906 tests across 201 explicit modules** in
668.072 seconds, with no failures/errors. Explicit module labels avoid ambiguous
discovery of several `tests.py`/test-package names. It used
`--settings=django_project.settings.test --keepdb --noinput` with a dedicated local
test database, `test_rokkad_rc_validation_20260924`. The module list and full log are
in ignored `.tmp/release-test-modules.txt` and `.tmp/release-candidate-tests.log`.
Four import-boundary unit checks, four JavaScript price-preflight checks, the tracked
application import guard, current-entry documentation links and whitespace checks
also passed. CI configuration is updated, but no remote GitHub workflow or repository
push was performed. Functional checks do not clear the security gate.

## Evidence and isolation

Server-only evidence and scripts are under
`/home/rokkad/deploy/rehearsal/release-candidate-20260924/`.
Disposable databases are `rokkad_rc_fresh_20260924` and
`rokkad_rc_upgrade_20260924`; the static volume is `rokkad_rc_static_20260924`.
The restored source is the verified pre-preference-retirement backup already on
the host. No database backup or customer-media archive was copied to OneDrive.
The running rehearsal remains on `rokkad:rehearsal-access-continuity-v2-20260924`.
The candidate was built and tested, not deployed or promoted to production.

## Other cutover requirements

Durable production credentials, actual login/owner/staff assignments, production
database/media target bindings, off-server recovery policy, remaining operator
acceptance and a fresh frozen-source import remain the cutover runbook's requirements.
Rehearsal grants and TEST-series activity must not be promoted as production data.
Razorpay/provider acceptance and servicing-only restrictions remain deferred;
explicit dated administrator access is the interim commercial-access mechanism.
