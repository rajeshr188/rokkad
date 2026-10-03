---
status: active
owner: project
updated: 2026-10-02
tags: [khata, docker, candidate, pilot, validation]
---

# Khata image verification and local test pilot

Later checkpoint: the owner's three collateral usability improvements are now
verified and running on localhost. See the
[updated image/UI evidence](khata-collateral-usability.md) for the current web image,
static volume and additional fictional browser accounts. The identities below
record this earlier image/recovery checkpoint; its source/archive are preserved.

The owner fixed/started Docker and instructed proceeding. The frozen candidate
now builds and passes Linux/runtime verification. A new fictional pilot is available
at **http://127.0.0.1:8077**. This is local operator review, not production or hosted
pilot activation. No repository commit/push, registry publication, production
migration, customer-data copy or external message/payment occurs.

## Exact identity

| Evidence | Identity |
| --- | --- |
| Frozen source candidate | `khata-local-20261002-8e030b414955` |
| Source inventory SHA256 | `8e030b4149558da31823106e116ceca05d7575c56b01464e0d94776dac386530` |
| Source archive SHA256 | `45252d8d40c3f15ae97603af00f5e935b30ee8308ddec03a7e49c27430cbe917` |
| Local image tag | `rokkad:khata-local-20261002-8e030b414955` |
| Verified local image ID | `sha256:a84bef3712092d0c99a67b0d0a697356551a0bccc3c9f8834248013b07d41bf3` |
| Local pilot workspace | `khata-73081a4c` / Khata container test pilot |

The build uses the verified 2,257-file frozen archive, the existing multi-stage
Dockerfile, pinned Python base and requirements constraints. `.dockerignore`
excludes local settings, credentials, backups/media, Git and documentation.
The revision label identifies the source snapshot rather than its older Git
baseline. Apt repositories remain external inputs; retain the actual image ID.
This is a local image ID, not an assertion of a published registry digest or remote CI.
Later documentation updates do not alter the frozen archive/application image.

## Verified boundaries

The fictional complete backup restores into PostgreSQL 16 on a new internal Docker
network. All **199 public tables / 1,287 original rows** match before pilot fixture
creation. Windows/Linux database collations order text differently: the original
Windows fingerprints are first rechecked against the unchanged fictional source,
then the same row bytes are sorted independently to form portable SHA256 checks.
The initial permissions-table mismatch is ordering, not modified data.

Preserved native evidence re-exports identically at its simulated original date,
and original private A4/label PDFs pass byte checks. A dedicated runtime login has
no superuser, BYPASSRLS or table-owner authority. Queries without Workspace context
return zero Khata rows; original/new-workspace software readiness checks pass.
Separate owner credentials are used only for restore, provisioning, schema checks
and tests. The production-profile startup rejects owner credentials with
`tenancy.E020`; the runtime web configuration contains no migration/owner credentials.

The image's non-root `app` user runs against a read-only root filesystem. Dependency
consistency, current migrations, no model drift and production-profile startup pass.
Production static collection copies 233 files and post-processes 643 entries.
**372 selected Linux regressions pass in 133.932 seconds**, including every Khata
workflow/calculation/recovery/document/label/correction/concurrency slice, adversarial
RLS/registry/storage checks and ordinary loan, Party/portal/dashboard, ticket/layout
and collateral-media preservation. Tests use a separate fictional database,
`test_khata_image_checks_20261002`, and separate test-media volume.

Actual Gunicorn HTTP checks verify owner/viewer username login, protected Khata
pages, 16 local static assets, missing-CSRF refusal, cross-workspace denial and
viewer servicing denial. The existing membership middleware may redirect a refused
cross-workspace request; the harness verifies refusal rather than imposing another
HTTP status. No authentication, membership or business-rule code change is made.

## Local pilot setup

Use usernames/passwords from the private, Git-ignored
`.tmp/khata-image-20261002/pilot-login.txt`. These are synthetic local credentials;
the owner account is an ordinary Workspace owner, not a platform superuser.
Google/OAuth and real email/provider workflows are not part of this local check.

The independent KH series has monthly `KH00001` and annual `KH00002`, both opened
on the actual setup day through ordinary approval and withdrawal services. Each
uses fictional INR 1 crore agreed limit, **1% per month**, 75% LTV, INR 1 lakh
actually withdrawn and a received/photo-backed Gold item. Limits/unused entitlement
stay distinct from actual debt. These are test inputs, not suggested customer terms.
Rates are fictional setup-day quotes; add a new fictional same-day quote before
cash/approval operations when reviewing on another day.

The production profile correctly requires secure HTTPS cookies. The localhost web
service uses the existing `django_project.settings.container_dev` profile for HTTP
review, with billing disabled and captured mail. Production-profile startup/static/
role checks are recorded separately. No application setting is weakened for production.

The application and database have only internal-network interfaces; PostgreSQL has
no host port. This Docker engine suppresses port publication on internal networks.
A small credential-free TCP relay publishes only `127.0.0.1:8077`, forwarding to
the fixed internal web container. It has no database credentials or media/settings
mounts. The web/database remain isolated from outbound providers. This relay is
local verification scaffolding, not a proposed production proxy.

## Persistence and recovery evidence

The initial verification database used disposable tmpfs. Before handing over the
pilot, its web writes were stopped and a local-socket `pg_basebackup` with SHA256
manifest was created. `pg_verifybackup` verifies the copy before and after transfer
into a new, confirmed-empty Docker volume. No network replication authorization
change was made. All public row fingerprints and every main-database sequence match
before/after the switch, including original roles and immutable source evidence.
The physical copy transfers **100,935,680 bytes**, covering this fictional cluster.
The database and web restart successfully, followed by passing actual HTTP checks.

| Resource | Name / purpose |
| --- | --- |
| Internal network | `rokkad-khata-image-20261002` |
| Database container | `khata-img-20261002-db` |
| Web container | `khata-img-20261002-web` |
| Local relay | `khata-img-20261002-gateway` |
| Persistent database volume | `khata-img-20261002-db-data` |
| Persistent private media volume | `khata-img-20261002-media` |
| Collected static volume | `khata-img-20261002-static` |
| Isolated test media | `khata-img-20261002-test-media` |

The old volatile database container remains stopped under
`khata-img-20261002-db-volatile`; it is not the current data store. Do not start it
or use it as recovery evidence. To stop/restart this local pilot, stop/start the
current gateway/web/database containers, preserving the named volumes. Do not
delete volumes when routine review ends. After a stop, start the database first,
then web and relay; confirm the login page works. Docker Desktop remains running.

Build, verification, Linux tests, private fixture settings/login and physical
backup/restart evidence remain in `.tmp/khata-image-20261002/`. The primary result
is `verification-report.json`; its local secret files must not be committed,
published or copied into a real deployment. This is same-machine test persistence,
not off-device or production backup acceptance.

## Remaining release acceptance

Complete [operator and 100 x 60 mm paper/QR acceptance](../flows/khata-test-pilot-acceptance.md),
including supported correction scope and statutory/default procedures. Phone QR
acceptance needs a reviewed address reachable by that device; a localhost URL on
the phone points to the phone itself. Do not mark paper scans passed from this UI test.
Hosted test deployment/TLS/operator bindings, independent/off-device recovery,
remote CI and owner activation acceptance remain open. Existing JCL/JSK/Lakshmi
production data and deployments are unchanged.
