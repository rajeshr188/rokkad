---
status: deployed
owner: operations
updated: 2026-10-12
tags: [dashboard, performance, loans, production]
---

# Shared dashboard performance release (12 October)

The authorized six-file dashboard optimization is deployed on top of MR-07.
Monthly loan evidence is loaded once per selector call and reused by the existing
native, recorded-anniversary and supported opening calculations. No financial
formula, posted evidence, policy choice, schema or cross-request cache changes.
See the [initial investigation and implementation](dashboard-performance-jcl-20261010.md).

## Exact scope and rollout

Production web and monitoring share rokkad:dashboard-20261012-f10d9c9c609e, immutable ID sha256:6aee177203fe236aa34295ff55ffee568125faf11044a2ddc3ce4e23ebf1bc06.
The source manifest delta is f10d9c9c609ec7219aa743067302cc4fa25c21bfed4fb3312865d89268bddf8e. Checkout ancestry is 6dc71e4a673751aaa19a658a9f326b9ba2427864;
the dirty checkout was not delivered wholesale. The six files are accrual_evidence,
obligation_state and continuation selectors, plus pawn_interest, pawn_tranches
and recorded_collections services. MR-07 monitoring changes are retained and
pending Party/portability work is excluded. No migration was applied.

Release completed at 12 October 2026 03:36:51 IST. Protected settings and credentials,
container environment/commands/mounts and worker resource caps remained identical.
The old worker stopped gracefully before the coordinated switch. The switch took
17.751 seconds; sampled HTTPS unavailability had an observed upper bound of
14.374 seconds. HTTPS, native/closed readers and all six timers recovered.
No operator financial posting or borrower notification was generated.

## Verification and recovery

- 114 exact-source financial, dashboard scaling/parity and MR-07 monitoring
  regressions pass; app boundaries, parsing and scoped whitespace checks pass.
- Fresh pre-release READ ONLY comparisons preserve every queue row/date/amount/note
  in all three lending Workspaces, using a repeatable-read snapshot and restricted
  role. Query counts are 13 per queue selector in each Workspace.
- The verified backup restored 202 tables/933888 rows into the explicitly isolated
  rehearsal database. All restored fingerprints matched. Startup, no pending
  migration/schema drift, native/closed readers and restricted isolation pass.
- The final bounded worker pilot completed actual turns for all three explicit
  Workspaces with zero errors. Financial source rows remained identical; graceful
  shutdown took 1.488 seconds with exit code zero. MR-07 startup/readers passed on
  the same database as the rollback checkpoint.
- The exact candidate image was encrypted off-server, downloaded, independently
  decrypted and loaded with matching identity. The recovery key stayed local;
  transient decrypted application-image files were removed.
- Verified pre/post backups are production-20261011T215837Z.dump and production-20261011T220704Z.dump. Remote-byte/recovery
  and capacity verification pass after removing the isolated database and staging
  copies. No retained backup or live database was removed. Free disk is 9.046 GiB.

Rollback stops monitoring and restores the rehearsed MR-07 web/worker image pair.
The schema is unchanged. Never restore older database contents over later staff
transactions. Safe local proof is retained in the ignored release folder; server
proof is under dashboard-release-20261012 in the established deployment root.

## Live dashboard measurements

After rehearsal cleanup and backup activity, direct view/template timings and
same-snapshot prior-code comparisons were measured in a separate READ ONLY process.
All queue digests match. These are single instrumented observations, not latency
or capacity guarantees; middleware, HTTP/CDN, assets and browser rendering are excluded.

| Workspace | Prior queue queries | Deployed queue queries | Prior view/template | Deployed view/template | Deployed view queries |
| --- | --- | --- | --- | --- | --- |
| jcl | 3980 | 13 | 9.436 s | 4.911 s | 77 |
| jsk | 1076 | 13 | 3.721 s | 2.277 s | 73 |
| lakshmipawnbroker | 4594 | 13 | 32.533 s | 3.956 s | 72 |

The remaining business overview folds all active event evidence synchronously;
queue row materialization also remains proportional to portfolio/history size.
Separately loading the overview is the next initial-render improvement. A financial
summary/cache requires explicit dates, freshness and mutation/reversal invalidation;
no such cache was introduced by this release. Saved risk refresh is not invoked by
the dashboard GET. Health freshness, financial support, book and valuation coverage
retain MR-07's separate completeness rules.
