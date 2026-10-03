---
status: active
owner: project
updated: 2026-09-30
tags: [plans, completed]
related: [../STATUS.md, ../archive/]
---

# Completed Work

## Storage media category correction (2026-09-30)

Current photo/document types now retain their category when ticket/import history
also references them. History-only and genuinely multiple-type files remain
distinct; ownership, deduplicated totals and cleanup references are unchanged.
Deployed with explanatory Workspace copy after 52 tests and candidate/live page
checks. Inventory 4 displays 2,303 JCL collateral photos instead of two; all six
Workspace category sums reconcile. Cleanup operator image was rebased and verified.
See [Status](../STATUS.md) for current images and dated snapshot counts.

## FW-015 reviewed offline cleanup workflow (2026-09-30)

Implemented `cleanup_storage` candidate listing, exact planning/private review,
verified recovery preparation, digest-approved execution, interrupted-run recovery
and create-only restoration. Existing active-superuser/restricted-role authority,
forced-RLS reference collection, reference-table locks, signed durable private
checkpoints and 50-object/64-MiB batch limits apply. Recovery has no automatic expiry.
Thirty new tests, nineteen regressions and the architecture check passed. Real R2
acceptance used two synthetic objects, which were removed afterwards. The operator
image is available on the server; production web and customer media were unchanged.
No production candidates in inventory 3. See [the runbook](../implementation/reviewed-media-cleanup.md).
Pricing, quotas, billing and online/automated cleanup remain explicitly deferred.

## Historical rehearsal retirement (2026-09-30)

Following owner approval, stopped/froze both exact historical scopes and compared
all 321 tables and 58,899 source objects with verified recovery. Fresh full archive
readback passed. Removed both source databases, two stopped hosted runtimes and
1,665,493,265 bytes of exact-manifest R2 media. Production's 29,770 references,
HTTPS, shared services and timers pass unchanged. Retain all five private recovery
archives (2.30 GB) without automatic expiry; old legacy server and unrelated billing
rehearsal remain. See [the retirement record](../implementation/rehearsal-retirement-20260930.md).
The subsequent reusable offline cleanup increment is recorded above; no real
production orphan batch was selected during retirement.

## Rehearsal recovery packages (2026-09-30)

Prepared both historical database/media/configuration packages, retained matching
application/PostgreSQL images and restore instructions. Isolated restores matched
321 public tables across both snapshots, reconstructed/hash-checked 58,899 media
files and resolved every checked current/historical media reference. All five private
R2 archive objects passed full SHA256 readback. Test resources were disposed of;
original environments remained at this checkpoint and were retired subsequently. See
[recovery evidence](../implementation/rehearsal-recovery-20260930.md) for limits,
exact scopes and private evidence locations.

## FW-015 committed-media retention prerequisite (2026-09-30)

Deployed Party default/gallery/document retention and removed unsafe physical
deletion from draft collateral attachment removal. Permissions, draft/renewal guards,
audit and failed-upload compensation remain intact. All 165 relevant tests and four
import-boundary tests passed; candidate/live checks each rendered 22 pages and six
deployed source hashes matched. No schema or destructive storage operation.
See [Status](../STATUS.md), the [decision](../adr/2026-09-30-retain-detached-party-and-collateral-media.md)
and the separate [cleanup/retirement plan](recoverable-media-cleanup.md).
Subsequent whole-rehearsal retirement and the reusable offline cleanup command are
recorded above. Actual production cleanup still requires an approved candidate batch.

## FW-015 storage visibility (2026-09-30)

Delivered prefix-scoped metadata inventory, forced-RLS Workspace summaries,
platform review classifications and dated usage/category displays. All 37 focused
tests, fictional desktop/mobile review, 22 production page checks and 16 source
hashes passed. The first scan found 29,770 objects / 880,056,600 bytes, all referenced
within the production application prefix. No deletion, quarantine or billing was
implemented. Broader cleanup remains future work; see [Status](../STATUS.md) and
[storage guide](../flows/storage-usage.md).

## FW-010 guided suspension/restoration (2026-09-29)

Deployed reasoned suspend/restore review screens, canonical restoration access
preview and lifecycle history. Existing authority, lifecycle/audit service and
commercial policy are retained. Signed, expiring confirmation prevents stale or
replayed actions. Thirty-seven focused tests, desktop/mobile review and 15
restricted read-only production renders passed. Server-only backup and rollback
artifacts are recorded in [Status](../STATUS.md). See the
[operator guide](../flows/platform-console.md) for use. Ownership recovery,
deletion and delegated platform roles remain separate work.

## FW-010 first platform console increment (2026-09-29)

Deployed read-only overview, searchable/paginated Workspace directory, current
access and invitation detail tabs, links to existing management workflows and an
operator guide. Sixteen focused tests, desktop/mobile review and restricted
production checks passed. Existing authority, trial/mail settings and business
workflows are preserved. See [Status](../STATUS.md) and the
[console guide](../flows/platform-console.md). The broader FW-010 role/delegation
and new-action backlog is not complete.

## Architecture Cleanup

- Contact stale Girvi loan references were removed or moved behind selectors/facades.
- Contact summary logic was separated from the `Customer` model.
- DEA facade boundaries were clarified and import tests were added.
- Girvi facade was introduced for cross-app reads.
- Girvi dashboard metrics were moved to `GivenLoan` / `TakenLoan`.

## Setup And Posting Fixes

- Rates were exposed through visible navigation paths.
- Rate-source setup became discoverable.
- Rate forms were upgraded with crispy helpers.
- Girvi disbursal handles missing voucher type setup and customer account provisioning through DEA facade helpers.

## Historical Implementation Phases

Archived completed phase notes:

- [Multi-tenant completed phases](../archive/multi-tenant/completed-phases/)
- [Root implementation reports](../archive/root/)
- [Girvi migration/refactor reports](../archive/girvi/)
- [DEA voucher/payment reports](../archive/dea/)
