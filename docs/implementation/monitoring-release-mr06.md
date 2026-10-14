---
status: deployed
owner: operations
updated: 2026-10-12
tags: [monitoring, deployment, workers, mr06]
---

# MR-06 coordinated monitoring release

This slice releases the MR-02–05 correctness and presentation changes together
with the existing recurring assessment command. It does not deploy the pending
portability, Party or dashboard optimization work. See the
[combined plan](../plans/combined-loan-monitoring-20261011.md).

## Independent release scope

The live baseline is BS-05 image
`sha256:7a81f9956bfe068029735375313480d96116a7b95b5b5e936fabd3af1fb65b49`.
The candidate overlays 27 monitoring runtime files, with a content-addressed
manifest and expected baseline hashes. Twenty-two of 24 inspected existing files
match local HEAD; the two setup files match committed `78335888`. Their candidates
contain only the monitoring changes on those verified baselines. The shared
PawnLoan model receives only the two MR-04 identity constraints, retaining its
existing positive item allocation rule. No source copy from production is needed.

Migration 0072 now depends directly on deployed 0068. Monitoring 0072–0073 and
pending portability 0069–0071 have disjoint schema changes. Local empty merge 0074
joins their leaves for the eventual combined checkout; it and the portability
migrations are excluded from this release. No applied migration is renumbered or
rewritten. The populated guard rehearsal tests 0068→0072 directly.

The owner-role READ ONLY live preflight found zero violations in all five retained
risk-reference categories and zero legacy resolved alerts without recovery events.
At this check, active loans totalled 6,753: JCL 2,637, JSK 1,601, Lakshmi 2,515.
These are dated inventories, not completed current assessment coverage.

## Worker operating contract

`scripts/start_monitoring.py` validates explicit positive, space-separated
`ROKKAD_MONITOR_WORKSPACE_IDS`, then applies the existing restricted-role and
pending-migration startup checks before execing the command. The previous singular
`ROKKAD_MONITOR_WORKSPACE_ID` remains supported when the plural setting is absent.
An empty or invalid configuration cannot enumerate all Workspaces or start work.

Initial settings are Workspace IDs `1 2 3`, ten candidates per Workspace turn,
five seconds between successful rounds and 300 seconds after empty/error-only
rounds. One process takes each Workspace in order. Per-loan transactions and row
claims are unchanged. Compose caps it at 0.35 CPU, 512 MiB and 128 processes, with
a 60-second stop grace period. These are conservative pilot settings, not a
demonstrated freshness SLA or large-scale capacity claim.

The command handles SIGTERM as a clean interruption and restores the prior
handler when it returns; non-main-thread callers do not install a signal handler.
An interrupted per-loan transaction unwinds through the existing transaction
boundary. Completed earlier loans remain committed. The final constrained pilot
stopped in 1.428 seconds with exit code zero, rather than Docker's forced kill.

Every completed turn logs Workspace, selected/current/error counts, local
assessment date and elapsed seconds. Monitoring posts no financial event and sends
no borrower notification. The worker preserves all valuation choices: missing
appraisals or quotes remain visible. A current calculation does not certify paper
books or make unknown valuation adequate.

## Release and rollback gates

1. Verify local startup, isolation, integrity, recovery and populated migration
   regressions; verify both the complete checkout and scoped image schema state.
2. Restore a checksum-verified backup into an explicitly isolated database. Run
   owner preflight and only 0072–0073, verify retained business-row fingerprints,
   restricted startup and representative direct/paper/imported readers.
3. Measure bounded worker behavior and foreground cost, retaining errors as
   errors. Verify source financial records and agreements remain unchanged.
4. Preserve the exact image encrypted off-server and independently recover it.
   Finish a current pre-switch backup and record protected configuration hashes.
5. Switch the web application and worker at the same checkpoint. Verify HTTPS,
   representative readers, derivative coverage, resource bounds and timers;
   renew exact-image backup acceptance and complete a post-switch backup.
6. Stop the worker before rollback. Do not restore an old database over later
   transactions or remove evidence guards. A previous image using an older
   assessment contract is not an approved permanent monitoring rollback: leave
   the worker stopped and forward-fix the compatible checkpoint. Rehearse any
   temporary reader recovery before claiming it works.

## Verified deployment

The coordinated release completed at **2026-10-11 20:29:14 UTC** (12 October IST).
Both web and the continuous worker run
`rokkad:monitoring-mr06-20261012-f4c02261abd0`, immutable image
`sha256:36dcac76cf8bec8dd42d154bcdf3f0b14d8b0068e90f4eb52c38fa2632a76e8c`.
The manifest delta is
`f4c02261abd05b00f9367f61045dbf6380c9c9683764d81bf585f9a542c0c5fc`,
with local source parent `6dc71e4a673751aaa19a658a9f326b9ba2427864`.
That parent is traceability metadata, not a claim that the dirty checkout was
committed or deployed wholesale. Pending portability/Party changes stay excluded.

Validation evidence:

- The 68 targeted regression checks, 39 final compatibility/deployment checks and
  17 final startup/shutdown checks passed. These runs overlap; they are not 124
  distinct tests. Full checkout and scoped-image model/migration checks passed;
  both disposable local test databases were removed.
- A checksum-verified production backup restored 202 tables/910,532 rows into
  the isolated rehearsal database. The two monitoring migrations preserved the
  201 retained business tables before assessment writes. Subsequent worker
  fingerprint comparisons excluded only the three derivative risk tables and
  the migration ledger; financial source rows and agreements remained unchanged.
- Migration 0073 retains a PostgreSQL `ORIGINAL_AGREEMENT` column default as well
  as the Django default. A historical model that omits the new column can still
  insert during the online upgrade window. No explicit valuation policy changed.
- Restricted-role startup, forced isolation, direct/paper/health/native readers,
  six native samples and closed-position browsing passed. Temporary prior-image
  startup and readers also passed against the upgraded isolated schema, with
  monitoring stopped. This is reader recovery, not permanent old-engine approval.
- The final resource-limited pilot completed turns for all three Workspaces with
  zero errors (2.464–3.713 seconds per ten-loan turn). Fifteen concurrent aggregate
  summary reads used at most three queries, with 0.094-second median and
  0.203-second maximum. These are narrow measurements, not whole-site p95 or a
  production capacity guarantee.
- The exact final application image was encrypted in private R2, downloaded,
  decrypted using the existing local protected recovery key and loaded with its
  exact identity verified. The key never left the computer. Transient decrypted
  files were removed. Earlier candidate evidence was kept separate.
- The fresh pre-switch checkpoint was `production-20261011T202446Z.dump`, SHA-256
  `1f4a2212b3fae1ee5c0c8cc50e260bc99a0167ca8929c64c39a642892e46543d`.
  Owner preflight passed again; only 0072–0073 applied (12.843 seconds). Web/worker
  switched in 20.463 seconds; sampled HTTP unavailability had a 15.651-second
  observed upper bound. HTTPS and all ordinary readers recovered successfully.
- Protected settings, runtime environment values, web command/mounts and backup
  credentials remained unchanged. No operator financial event was posted.
  All six existing timers resumed; monitoring is a continuous container, not a
  seventh timer. Web and worker had zero restarts at final verification.
- Exact-image recovery acceptance and the post-switch backup passed. The latter
  is `production-20261011T202936Z.dump`, SHA-256
  `c8029685bedc2c706f81d1d4a562cd89d84a0a7d4f6f8bd9774be9c2bf0c13f9`.
  Remote download and retention verification passed with no low-space warning.
  Only the isolated rehearsal DB/dump and duplicate encrypted staging files were
  removed; retained backup objects and the live DB were unchanged. Final free
  capacity was 9.063 GiB.

An initial deployment-helper baseline comparison stopped before migration because
it did not normalize CRLF like the manifest/build verification. The helper was
corrected to use the same normalized comparison; protected configuration hashes
remain byte-exact. No source change or baseline discrepancy was bypassed.

## Initial coverage and remaining work

At **20:32:08 UTC**, 38 completed production turns had zero errors and took
2.288–4.082 seconds. The first completed turn arrived 35.324 seconds after the
worker container started, including restricted-role/schema startup. Subsequent
turns progressed across all three explicit Workspaces. This is measured startup
delay, not a guarantee that every pending loan is refreshed within that interval.

| Workspace | Active | Current | Stale | Unassessed | Errors |
|---|---:|---:|---:|---:|---:|
| JCL | 2,637 | 132 | 52 | 2,453 | 0 |
| JSK | 1,601 | 130 | 147 | 1,324 | 0 |
| Lakshmi | 2,515 | 132 | 0 | 2,383 | 0 |

The 394 current assessments are initial catch-up evidence, not finished coverage.
At the initial measured pace, the first backlog is roughly an hour's work; this
estimate must be checked against later turns and actual failures. Normal idle
polling is five minutes, plus queue/processing time for pending loans. Daily
rollover makes the prior day's projections pending again. Eligible source changes
use the existing invalidation/refresh paths; visiting a summary does not recalculate
every loan.

A bounded ordinary service refresh separately verified active RA00500, C07557,
D01622 and D01623 without financial posts. Each has a current supported financial
calculation. JCL C07557 has usable valuation and complete transaction evidence;
RA00500 and the two Lakshmi paper loans retain unknown valuation and provisional
paper-book coverage. JSK 06716 remains closed and readable. Current calculation
does not erase these evidence distinctions.

The final 15 production summary reads used at most three queries, with 0.050-second
median and 0.058-second maximum. Portfolio totals were still incomplete in all
three Workspaces because catch-up and evidence coverage are incomplete. The worker
does not supply missing appraisals, change valuation choices or certify paper books.

MR-06 release/activation gates are complete. MR-07 remains the next slice: measure
and reduce repeated source reads/repricing, using observed worker delay and
foreground cost. Full launch-scale testing remains deferred. The protected server
proof directory is `mr06-release-20261012` under the existing deployment root;
its exact-image, rehearsal, switch, final, cleanup and backup reports are retained.
