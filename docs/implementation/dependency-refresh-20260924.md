---
status: active
owner: project
updated: 2026-09-24
tags: [release, dependencies, security, rehearsal]
related: [release-candidate-20260924.md, linode-production-cutover.md]
---

# Dependency refresh verification

The owner updated the local environment and requested verification and the next
release step. The requirements files had remained unchanged. Fourteen direct pins
and their constraints now capture the installed updates; PyJWT was additionally
updated from 2.9.0 to 2.15.0. The previous Linux-only transitive constraints remain
unless their direct requirement changed. This is a dependency refresh, not a change
to loan calculations, subscription policy, RLS or production routing.

| Dependency | Updated pin |
| --- | --- |
| Django | 6.1.1 |
| django-allauth | 65.19.4 |
| django-select2 | 8.4.8 |
| cryptography | 50.0.1 |
| PyJWT | 2.15.0 |
| Pillow | 12.3.0 |
| requests | 2.34.2 |
| urllib3 | 2.8.0 |
| idna | 3.20 |
| sqlparse | 0.6.0 |
| tablib | 3.10.0 |
| django-import-export | 4.4.1 |
| django-money | 3.6.0 |
| diff-match-patch | 20241021 |

## Security and compatibility evidence

The clean Linux image built from `6e1c2d33` passed `pip-audit`: **71 distributions
checked, zero skipped, zero known advisories**, without an ignore list. Audit tools
ran separately without deployment credentials or customer-data mounts. This clears
the earlier candidate's known Python dependency findings for the scanned versions;
it is not a claim that the entire application or operating system is vulnerability-free.
The same unsuppressed scan passed on the corrected final image `fd011920`.

The earlier no-fix PyJWT entry, [PYSEC-2025-183](https://github.com/pypa/advisory-database/blob/main/vulns/pyjwt/PYSEC-2025-183.yaml),
is disputed upstream and lists 2.10.1 as its last affected version. Rokkad has no
first-party JWT encode/decode implementation; the Google provider uses allauth's
verification path. PyJWT's [release history](https://pyjwt.readthedocs.io/en/stable/changelog.html)
documents subsequent key-validation and parsing hardening. No advisory was suppressed.

[Django 6.1](https://docs.djangoproject.com/en/6.1/releases/6.1/) supports Python 3.14.
[Allauth's release notes](https://docs.allauth.org/en/latest/release-notes/recent.html)
were reviewed for authentication changes. The app's existing proxy trust settings
were not broadened. New mocked-provider tests exercise valid Google RSA identity,
wrong signing keys, audience/issuer/expiry rejection, HMAC/RSA mismatch rejection and
claim checks after a TLS-protected token exchange. No real OAuth, mail or payment
request is sent. The HMAC/RSA mismatch raises TypeError in this library combination
rather than allauth's OAuth2Error; the test records rejection, not normalized error UI.
These tests are included in CI; real interactive Google login remains an operator
acceptance check.

Local `pip check`, Django system checks and five new Google token checks passed.
The first broad run completed 1,906 tests with one compatibility failure: Select2
8.4.8 now creates its default cache token during `build_attrs`, overwriting the
borrower widget's signed URL token set by `render`. The widget now installs its
stateless URL-bound token after the base attributes are built. The existing complete
test passes with added rendered-token assertions, preserving unavailable-cache,
separate-worker, expiry, malformed-token, cross-Workspace and permission-denial checks.
This fixes borrower search without relaxing authorization or adding shared cache state.

Fresh/restored migrations and restricted-runtime checks passed with 116 existing
business/preference/identity tables preserved: 99 business/subscription, five retained
preference/audit and 12 user/membership/social-account tables. The final image passed
non-root startup and static collection, restricted-role checks, owner-role rejection,
both draft-product creation/rollback paths, borrower searches in all three restored
Workspaces, a synthetic allauth password-login form submission, subscription boundaries
and existing JCL/JSK PDF checksums. All synthetic data was rolled back. The final full
regression passed **1,911 tests across 202 modules** in 684.503 seconds, including
the borrower-search correction and five new Google token tests. Local evidence is
in `.tmp/dependency-candidate-tests.log` and `.tmp/dependency-test-modules.txt`;
the aggregate result is retained with server-side evidence. App-boundary, current
documentation-link and whitespace checks passed. No remote GitHub workflow was run.

## Release evidence

Build and validation evidence stays under the server's
`/home/rokkad/deploy/rehearsal/dependency-refresh-20260924/` directory. Isolated
databases are `rokkad_deps_fresh_20260924` and `rokkad_deps_upgrade_20260924`.
The restored upgrade includes business, retained preference, user, membership and
social-account row fingerprints. No sensitive backup is exported to OneDrive.

Final candidate:

- Source: `fd011920`, branch `release/2026-09-24-rc1`.
- Image: `rokkad:rc-20260924-fd011920`.
- Image ID: `sha256:55ad097dc208746fed3f9417a68e357e13c2062f979c89a099087f2458fad934`.
- Source archive SHA-256: `948329ec2ea04db677d8c7ae7a3a36353f942d77ba0c3db3eeb3dd2ad6a5fc3b`.

## Rehearsal deployment completed

The verified image is running at `https://rehearsal.rokkad.com`. The pre-deployment
plan confirmed no pending schema operations. Web was paused for a private server-only
database backup, owner-only migration check, static collection and rollback-only
acceptance probes, then reopened on the exact verified image. HTTPS home and login
checks passed. All **117** checked existing business, preference, user/membership,
social-account and access-decision tables retained their row fingerprints.
Synthetic password login, borrower searches in all three Workspaces, subscription
access controls and saved JCL/JSK PDF checksums passed. No financial mutation or
external provider call was performed.

Backup metadata is in `evidence/backup.json`; its SHA-256 is
`30335df13e9ff2b55647845852cc77d5ef1a6d0ed174554342d6c466af2360b9`.
The old compose file is `evidence/web-compose.before.yml`; the old image remains
`rokkad:rehearsal-access-continuity-v2-20260924`. If rollback is needed, restore that
compose image and recollect static assets using it before reopening web. No schema
reversal or database restore was needed for this release. Backups remain on the
server, as instructed.

The earlier dependency-advisory blocker is cleared for this candidate. Production
routing is unchanged. Remaining work is operator acceptance (including actual login
and staff workflows), reviewed production credentials/proxy and recovery settings,
and the complete frozen-source import/cutover runbook. The existing HSTS deployment
warning remains part of production proxy review. Payment-provider acceptance stays
deferred with checkout disabled and dated administrator access available.
