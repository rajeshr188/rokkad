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
checked 72 distributions with zero skips and reported advisories for 11 packages:

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

Assembly checks are in progress. Record final source/image identity, regression
results, fresh/upgrade migration evidence and runtime-role checks here before
describing the candidate as technically verified. A successful build does not clear
the security gate above.

## Other cutover requirements

Durable production credentials, actual login/owner/staff assignments, production
database/media target bindings, off-server recovery policy, remaining operator
acceptance and a fresh frozen-source import remain the cutover runbook's requirements.
Rehearsal grants and TEST-series activity must not be promoted as production data.
Razorpay/provider acceptance and servicing-only restrictions remain deferred;
explicit dated administrator access is the interim commercial-access mechanism.
