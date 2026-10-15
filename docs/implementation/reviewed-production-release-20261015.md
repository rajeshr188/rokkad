---
status: complete
owner: project
updated: 2026-10-15
tags: [release, review, production]
---

# Reviewed production release, 15 October

The owner requests review, commit, push and deployment of the accumulated source
changes. This authorises the combined software release and supersedes the earlier
origination-only rollout scope. Actual customer edits, register reservations,
WhatsApp activation and provider configuration remain separate business actions.

## Completed production result

The coordinated switch completes on **15 October 2026, 09:52:50 IST**. Application source
`26badab21a4c264022cee412ddcf923a44450b8b` is pushed on `work/loan-servicing-contract-ld01`.
All six groups pass in [the complete CI run](https://github.com/rajeshr188/rokkad/actions/runs/38676529405): foundation/image,
Workspace/first-loan, billing/mail, Rates, portability/WhatsApp and Loans. The full
Loans group includes 2,478 cases; group counts can overlap and are not summed as
distinct tests. All observed integration failures are resolved.

Web and monitoring run `rokkad:review-20261015-26badab21a4c` with image ID
`sha256:e09f5847034add44eb68d7ecff2fca3ddb008c522d1a9c83e86fcf485a3bd918`. Exact committed-source verification passes for all 1,867
runtime files in each reader. Three mail commands and the health reader use the
same image and verified static volume. Runtime environment values and protected
configuration stay exact; only the reviewed image/static bindings change.

Post-start acceptance initially stopped because Docker names the new image's user
`app`, while the older derivative expressed the same UID as `10001`. Forward
acceptance verifies the effective UID is 10001 in both readers and proves their
original environment values, commands and mounts. Compose's null command is
resolved to the inherited image command. No configuration values change and no
database restore or downgrade occurs; timers resume after compatible reader
checks complete.

The final production-copy rehearsal restores 1,066,815 rows in
204 tables and preserves all 201
original business projections. Its four owner migrations take
55.727 seconds. Live deployment applies those same four
WhatsApp migrations, preserves all 201
original business projections, refuses owner startup, and passes restricted
read-only readers before restarting compatible services. The private checkpoint,
raw diagnostics and row fingerprints remain on the server. Only non-customer
verification metadata is collected locally.

Independent encrypted remote download, local decryption and exact image reload
pass; the recovery key never leaves the owner's machine. Final HTTPS, role,
schema, source and full-reader-lifetime log checks pass with six active timers.
The post-release operational backup, encrypted remote verification and retention
pass. About 19.25 GiB remains free, clearing the earlier capacity warning.
Regenerable builder cache cleanup preserves every image and volume; protected
older backup checkpoints remain retained. The verified disposable rehearsal DB
is removed while all backups and proofs remain.

The JCL/JSK/Lakshmi audited grants remain full through 22 October, 23:39:08 IST
(fractional seconds retained). Subscription dates, entitlements, invoices and
payments remain unchanged by the release. WhatsApp inbound, intent and dispatch
activation remain disabled; live sender approval/pilot acceptance is separate.
Bronze software is available without creating a quote or amending a policy.
V9 assessments refresh through the ordinary bounded monitoring worker; this does
not attest that books are complete or collateral coverage is sufficient. Actual
borrower corrections, number reservations and other financial business actions
are not performed by the deployment.

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
The expanded combined suite approaches the former 45-minute job limit. The same
six groups now run as ordinary parallel matrix jobs with independent PostgreSQL
services, schema/runtime checks and a 60-minute limit per group. Fail-fast is
disabled and no coverage is removed. This also makes a completed group's failure
diagnostics available while the remaining groups continue.
The isolated bronze UI fixture also needs the storage override from the setup
class whose methods it reuses. Native-settings confirmation passes after adding
it. Test settings now explicitly use local media and unhashed assets so ordinary
test uploads cannot inherit a developer's real R2 backend. Production static
manifest collection remains covered by the independent image/rehearsal gates.
The full 2,478-case Loans group exposes three dated continuation fixtures that
must align their clock with the live-only refresh boundary, plus two assertions
for the former release label. Six focused confirmations pass with the clock
aligned and the common Close / release loan route asserted. The current-date
guard, settlement, custody, export and financial assertions remain intact.

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
warning. The completed result above records acceptance of these gates.
