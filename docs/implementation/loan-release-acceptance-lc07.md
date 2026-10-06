---
status: active
owner: project
updated: 2026-10-06
tags: [loans, release, verification]
---

# LC-07 release acceptance

Technical preparation and recovery checks pass locally. This records the fictional
local rehearsal; the subsequent
[publication and live-source verification](loan-candidate-publication-20261006.md)
supersedes its publication/access state. Real production-copy recovery, complete
source-book/staff acceptance and deployment remain unperformed. The
[operator release guide](../flows/loan-continuation-release-acceptance.md) records
the exact gates and current acceptance matrix.

The read-only `check_loan_release_inventory` command builds dated Workspace
cohorts from existing continuation, transaction-completeness, evidence-quality,
common eligibility and archive-directory selectors. It does not refresh monitoring
or write financial/source evidence. PostgreSQL enforces a repeatable-read,
read-only snapshot. Unsupported positions have no invented balances; partial
history, terminal position and unadmitted source identities remain explicit.

The existing application-boundary check exposed direct billing-model imports in
four test fixtures. Those operations now use the existing tenancy test helper.
Statutory auction fixtures now originate through genuine approval/disbursal and
retain one origin, replacing fake ACTIVE rows and fabricated disbursal events.
No business workflow or billing authority changes.

Private local evidence is retained under `.tmp/lc07-20261006/`. The recovery drill
uses `joint_loans_20261003`, a fictional local acceptance database, and new targets
only. It is not the current JCL/JSK/Lakshmi production database. Candidate source
is frozen with per-file hashes without committing or publishing changes.

## Verification

- **225 release-focused regressions pass** (252.483s): four admission paths,
  terminal evidence, continuation and quality, shared interest, quote age,
  generated LD-08 scenarios, runtime entrypoints and portability/recovery.
- **87 final regressions pass** (64.917s): corrected Khata fixture suites,
  statutory notice/auction origin, tenancy and five release inventory cases.
  Earlier fixture failures were corrected before this complete clean rerun.
- Application boundaries pass for 1,054 tracked Python files; all four static
  boundary-unit tests pass. Changed/new Python and runtime JSON contracts parse,
  current documentation links pass, and whitespace checks pass.
- The inventory command rejects attempted UPDATE with PostgreSQL SQLSTATE 25006,
  produces no partial output, preserves the row and clears Workspace/read-only
  transaction state. The full JSON and summary command both execute successfully
  under restricted runtime in the isolated migrated candidate.
- A full database/media restore matches **202 public tables and nine media files**
  exactly before migration. Candidate migrations apply through owner-only settings;
  a post-migration dump cold-restores into a second new target with exact fingerprints.
  Source fingerprints remain identical. Restricted startup, pending-migration
  rejection, owner-startup rejection and no schema drift pass.

The offline build failed because dependency layers were not cached. The normal
clean build subsequently succeeded with dependency downloads enabled. Both logs
are retained. The final frozen source is refreshed after fixture corrections;
the final image's startup/schema/contract-resource checks reuse the verified
restores without changing financial data. Manifest/image identities remain private
in `.tmp/lc07-20261006/`; this is an uncommitted local candidate, not a release tag.

## Local cohorts and remaining gates

The restored fictional source has 15 ordinary recorded loans (10 active, five
closed) in Workspace 1 and an empty Workspace 2. Eight use `recorded-anniversary/1`
and seven use `/2`; their saved legacy semantics remain unchanged. Two assessments
are stale and 13 unassessed; all valuations are unassessed. Book coverage is nine
unconfirmed, four behind and two confirmed. Calculation support does not erase
these independent evidence limits. No archives exist in this fictional source;
actual archive retention/admission boundaries are covered by the terminal test.

These counts are not production JCL, JSK or Lakshmi counts. Production inventory,
unsupported-case disposition and real staff/source acceptance remain pending.
The owner supplied **JCL RA0500** as the first real acceptance reference. Its
actual figures/entry channel have not been retrieved or checked against source;
no authenticated production browser/database session was available in this run.
A Lakshmi paper reference and actual staff confirmation remain pending.
Before deployment, verify committed/CI identity, all web/worker readers, the current
production migration plan and backup, and production/off-device recovery. No
deployment, source conversion or source-book acceptance has occurred.
