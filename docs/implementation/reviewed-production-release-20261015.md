---
status: active
owner: project
updated: 2026-10-15
tags: [release, review, production]
---

# Reviewed production release, 15 October

The owner requests review, commit, push and deployment of the accumulated source
changes. This authorises the combined software release and supersedes the earlier
origination-only rollout scope. Actual customer edits, register reservations,
WhatsApp activation and provider configuration remain separate business actions.

## Reviewed scope

The source includes portable origination and corrections, current risk evidence
and recovery, bronze/reference-price valuation, account verification and guided
business setup, Party merge search, owner WhatsApp delivery controls, and their
tests, migrations, contracts and documentation. The existing production
origination image already contains part of this work; the new candidate must be
built from the complete committed source with an OCI revision label.

The review excludes retained debug files under root `tmp/` and private `.tmp/`
task folders. New documentation screenshots use fictional owners and customers.
Python syntax and credential-pattern inspection pass. The review fixes the CI
JavaScript command, extends CI coverage to newly added apps and journeys, and
uses a real request fixture for the legacy-review template now that it includes
guided navigation. The large exchange-volume test remains included in Linux CI;
its tag only permits separate execution on Windows.

The first combined CI run exposes stale integration fixtures: the first-loan
journey must request the complete dashboard rather than its lazy shell, the plan
page shell needs a session and isolates account guidance from its fake user, and
archive navigation now uses the existing Completed closures label. The fixes
retain financial lifecycle assertions and check both permitted and denied archive
links. The release remains gated on a new complete passing CI run.
The next run passes all 364 Workspace/first-loan checks and exposes the isolated
pricing template engine's missing navigation library. Its real request fixture
now supplies anonymous authentication and session state; all five pricing tests
pass. Independent CI test groups continue after a failure once schema setup
succeeds, while any failure still fails the job.

## Release gates

The corrected integrated test discovery uses the repository as its top-level
directory. CI must pass on the pushed source revision, including Loans, platform
WhatsApp, portability (including the full exchange-volume case), onboarding,
billing, Rates, tenant isolation, model consistency and image startup. Local
browser interaction checks pass all 19 cases; helper checks pass all 14 cases.

Production-copy rehearsal must preserve every original business table projection,
apply only the four pending WhatsApp migrations, verify restricted startup and
read-only business views, collect static assets into a separate volume, and prove
source financial rows remain exact after bounded monitoring. The candidate image
must survive encrypted remote download, local decryption and exact image reload.
The recovery key and raw production evidence remain private.

The coordinated deployment pauses the existing scheduled readers, web and
monitoring, makes a fresh private checkpoint, applies owner-only migrations and
switches all compatible readers. Original runtime configuration and the three
audited grace extensions through 22 October, 23:39:08 IST must be preserved.
WhatsApp inbound, source-intent and dispatch activation remain disabled. Bronze
support adds no quote or policy configuration automatically. The monitoring
calculation version advances to V9; old assessments remain visibly outdated until
the ordinary bounded worker reassesses them.

Final acceptance requires exact committed runtime source, no pending migrations,
restricted database roles, healthy HTTPS, six restored timers, clean reader logs
and a successful operational backup with verified encrypted remote retention.
Protected older checkpoints must remain retained despite the existing disk-space
warning. Deployment results will be recorded here after these gates complete.
