---
status: accepted
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, concurrency, performance]
related: [../plans/loan-boundary-simplification-20261016.md, ../implementation/loan-boundary-ls06-20261016.md]
---

# Retain monitoring guards; narrow the policy Workspace lock

LS-06 measures local synthetic source invalidation and worker contention before
changing mechanisms. Repeated rate saves rewrite already-stale assessments; the
original 2,500-row restricted-role case takes about four seconds. A trial that
separately locks non-error rows and updates only CURRENT rows demonstrates no
useful improvement at that size and makes first invalidation slower. It is removed.
Concurrency testing also reproduces a real policy/assessment deadlock on the
original implementation, which warrants a focused lock-mode correction.

## Decision

Keep source invalidation, per-loan worker claims and source fingerprints unchanged.
Change only the monitoring-policy setup service and database guard's Workspace
row lock from FOR UPDATE to FOR NO KEY UPDATE. This still serializes setup writers
and conflicts with existing lifecycle/ownership FOR UPDATE locks, but is compatible
with KEY SHARE foreign-key checks when the worker appends risk evidence.

The reproduced cycle is: policy writer owns the Workspace FOR UPDATE lock and
waits for a snapshot; worker owns the snapshot and needs a Workspace KEY SHARE
lock to insert its immutable transition. The narrower parent lock breaks this
cycle without discarding transitions or weakening policy history checks.

A CURRENT-only invalidation update is unsafe. A worker can hold a
STALE snapshot just after its final source fingerprint check and before publishing
CURRENT. An invalidator that skips that stale row can miss the newly published
result. Existing non-error scope updates preserve serialization: either
the committed source enters the worker's fingerprint check, or the source writer
waits and invalidates the worker's published result. Real PostgreSQL tests exercise
both the earlier rate-change rejection and the late rate/policy lock race, and
retain the existing competing-amendment tests.

Do not use skip-locked invalidation or on-commit callbacks. Failed invalidation
still propagates and rolls back the source transaction. Scope/date/metal
applicability, error retry semantics, financial evidence and V11 remain unchanged.

## Consequences and limits

Broad invalidation still rewrites matching non-error rows, including stale ones.
The bounded measurements do not justify a revision mechanism or shorter worker
claim. They identify a cost for later representative profiling. The source-change
diagnostic remains a refresh instruction, not a complete source-change history.

Worker same-loan serialization remains. Local measurements establish no production
SLO, large-scale capacity, heavy-history throughput or universal absence of race
conditions. Financial writes still depend on monitoring-table availability; this
slice documents and tests that dependency rather than claiming full storage
decoupling. Any later revision-based replacement must prove equivalent freshness,
date, correction, rate/policy scope and concurrency guarantees. The separately
shelved launch-capacity programme is not resumed.

Migration 0086 replaces only the historical policy guard function's lock mode,
with an exact reverse. It branches from deployed 0084 so it need not deploy pending
financial corrections; 0087 only joins the full checkout's graph. The service and
database guard must both use the narrower mode. No table, policy data, portable
profile or V11 change. Matching application readers must still be released
together for earlier LS slices. See the
[measurement and verification record](../implementation/loan-boundary-ls06-20261016.md).
