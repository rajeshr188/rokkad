---
status: active
owner: project
updated: 2026-10-02
tags: [khata, candidate, pilot, recovery, validation]
---

# Khata test candidate and fictional recovery rehearsal

Later checkpoint: the owner fixed/started Docker. The
[image/local pilot review](khata-image-pilot-20261002.md) supersedes this checkpoint's
Docker blocker with a verified Linux image and persistent localhost pilot.
Hosted/physical/off-device/owner acceptance remains separate.

The owner selected a **new test workspace** and retained **100 x 60 mm** labels.
Local preparation uses an independent KH test series. No production/customer
workspace, real financial record or production migration is touched. Hosted test
deployment and physical operator acceptance remain separate steps.

## Source freeze

`scripts/prepare_khata_candidate.py` captures current tracked and untracked source
from explicit application/static/template/locale, documentation and CI/script
allowlists. It excludes environment files, Git history, customer media, database
backups and local outputs. It records a SHA256 for every member, the inventory,
archive checksum, current Git baseline and a content-derived local candidate ID.
It reads the archive back and refuses a source/inventory change during capture.
Fixed member timestamps and ordering make unchanged captures byte-identical.

This is a frozen **local source snapshot**, not a committed release or verified
container image. It includes the accumulated earlier local changes; the current
Git commit alone does not identify that code. No Git staging, commit, push or
deployment is performed. The final identity/inventory/checksum is retained in
`.tmp/khata-test-candidate-20261002/manifest.json`, alongside `source.zip`.
Later code changes require a new snapshot and appropriate validation.

```powershell
.venv314/Scripts/python.exe scripts/prepare_khata_candidate.py --output .tmp/khata-test-candidate-20261002
```

Extract the verified archive into a new disposable build directory and use its
ordinary Dockerfile with the manifest candidate ID as `ROKKAD_REVISION`. Retain
the resulting image digest separately; do not label a dirty snapshot as its Git
baseline commit. The existing CI uses the pinned requirements and ordinary image
build. Remote CI and image/runtime verification remain required before promotion.

## Repeatable fictional recovery drill

`scripts/rehearse_khata_recovery.py` creates three **new** local PostgreSQL databases,
each under its hard-coded `test_rokkad_khata_drill_` prefix. It rejects an existing
name, non-ASCII/non-alphanumeric suffix and non-local database host. It never accepts
a customer source database, overwrites a destination or drops a database. The
local owner/superuser connection is used only for disposable database creation,
migrations, complete fingerprints and offline recovery. No credentials are printed
or included in the evidence report.

```powershell
.venv314/Scripts/python.exe scripts/rehearse_khata_recovery.py --run-id 20261002d
```

The fixture intentionally reuses the regression suite's fictional service inputs,
without a TestCase rollback wrapper. It writes durable evidence through the real
services: active monthly borrowing with pending exchange return, a distinct annual
agreement, and a closed agreement with an original receipt, compensating correction,
replacement receipt, settlement and physical handover. Photos, a combined label,
statement and settlement receipt are stored using filesystem storage. Simulated
dates are 10 October/10 November 2026. These are not historical paper imports or
real future financial entries.

The full drill applies owner-only migrations from an empty database, captures a
custom-format pg_dump and private-media ZIP, and independently reconstructs both
into a new destination. Every public table's ordered row content/count and all
PostgreSQL numbering sequence states must match. Every saved file's path, size
and SHA256 must match; native reconciliation and original PDFs must re-export
identically. Capture checks source rows/media for changes and has no other writers.

A second fully restored disposable database then simulates the documented empty
Khata destination by removing only its thirteen fictional Khata tables' rows with
owner guards suspended transactionally. This is test scaffolding, not a production
repair or merge. Native preview must leave no rows or files. Native commit must
preserve full row fingerprints, original media and canonical P/U/interest/custody.
Ordinary sequences remain exact; Khata PK sequences may advance but must never
move backwards. An unused Khata sequence can become called at 1 during safe restore;
the first stricter sequence assertion was corrected to enforce this existing
monotonic contract rather than demand unchanged unused-counter state.

Finally, a NOLOGIN/NOSUPERUSER/NOBYPASSRLS role receives only ordinary runtime
table/sequence grants. `SET ROLE` checks zero Khata rows without Workspace context,
all software readiness checks, original private PDF reprints and an actual new
fictional withdrawal after recovery. This verifies effective SQL role restrictions;
it does not certify a deployed web/worker login or container configuration.

Evidence remains in `.tmp/khata-recovery-20261002d/`: `report.json`, public-table
fingerprints, media inventory, migration logs, database dump, private-media/native
archives and reconstructed files. Only fictional data is stored locally. The
disposable databases and role remain inspectable. The tool deliberately contains
no automatic deletion; choose a separately reviewed cleanup scope when finished.

## Limits and next gates

Final run `20261002d` passes: **199 public tables / 1,287 rows**, **196 numbering
sequences**, and **4 private media files / 139,718 bytes**. Full database/media
reconstruction, exact full sequence state, native preview rollback, committed
source/media reconciliation, monotonic Khata/unchanged ordinary sequences and
restricted-role readiness all pass. No Workspace context returns zero Khata rows;
verified original PDF downloads and a post-recovery withdrawal succeed. The new
local test workspace is `khata-83f6003f` (display name `Khata test pilot 20261002d`).
Three fictional agreements cover active monthly, active annual and closed custody.

Two unchanged trial source captures are byte-identical; the final snapshot is
captured after documentation/fixture-inventory updates. Four boundary unit tests,
the 841-tracked-file supported-app scan, dependency consistency and operator-script
syntax checks pass. Prior Khata/ordinary regressions remain the
[label review's evidence](khata-release-review-20261002.md); this slice changes
rehearsal/source tools and documentation, not lending services or calculations.
Final Django system/migration consistency checks pass on the disposable source:
no issues (one existing silenced check), no model drift. All current application,
static, template and locale build inputs are covered by the source allowlist;
928 local documentation links across 36 current/Khata files pass.

Earlier `20261002b`/`20261002c` scratch databases/evidence also remain from verification
development. All are fictional under the same exact drill prefix. The primary
acceptance evidence is `20261002d`; do not confuse old manifests or partial runs
with the final report.

The software checks do not replace a hosted candidate's independent/off-device
backup retrieval or a production recovery drill. They do not certify real logins,
external delivery, provider payments, regulatory/default processes or a printer.
Existing JCL/JSK/Lakshmi workflows and numbers are untouched by the rehearsal.

Docker Desktop is installed locally but its engine reports that it cannot start,
including after permitted normal startup and engine checks. A clean local Docker
config avoids reading personal Docker credentials. No image has been built or
published; verify the frozen source using a functioning local or isolated build
environment before hosted test deployment.

Follow [test-pilot acceptance](../flows/khata-test-pilot-acceptance.md) for operator
and paper QR results, scope acceptance and compatible servicing/forward-fix review.
Do not automatically close the remaining gates in the
[release review](khata-release-review-20261002.md).
