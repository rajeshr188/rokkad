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
The broad regression, fresh/restored migration and runtime checks are in progress.

## Release evidence

Build and validation evidence stays under the server's
`/home/rokkad/deploy/rehearsal/dependency-refresh-20260924/` directory. Isolated
databases are `rokkad_deps_fresh_20260924` and `rokkad_deps_upgrade_20260924`.
The restored upgrade includes business, retained preference, user, membership and
social-account row fingerprints. No sensitive backup is exported to OneDrive.

Record the final candidate identity, regression results and rehearsal deployment
here when verification completes. Production cutover remains a separate operation.
