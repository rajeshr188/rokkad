---
status: deployed
owner: loans
updated: 2026-10-12
tags: [monitoring, performance, risk, mr07]
---

# MR-07 measured monitoring efficiency

The [combined monitoring plan](../plans/combined-loan-monitoring-20261011.md)
calls for measured reduction of repeated source reads and repricing after the
[MR-06 worker release](monitoring-release-mr06.md). This slice changes five runtime
files and adds regression coverage. It does not add models, migrations, a queue,
cross-request caches or a new assessment-history workflow.

## Finding and smallest change

The existing source-checked refresh calculated exposure once, but delinquency
separately re-read/folded balances, schedule and obligations. Risk then re-read
schedule maturity and transaction coverage; the writer checked coverage again.
For collateral it fetched a metal quote and latest approved appraisal per item.

Exposure's existing source loading now returns private, frozen financial inputs:
the scoped loan, reporting date, continuation, schedule and obligation state.
An ordinary refresh passes those inputs to exposure, delinquency and risk. Each
consumer validates the loan, reporting date and active Workspace before use.
Transaction coverage is computed once after successful financial/valuation reads
and reused for the risk result and its saved provenance.

These inputs last only for the calculation. The initial/final source fingerprints,
current-date checks, loan locks, per-loan transaction boundary, access checks,
immutable risk events and error/recovery behavior remain in place. The final
fingerprint must still match before prepared coverage is persisted. A book-evidence
failure retains already-supported financial diagnostics but saves ERROR with no
usable exposure, DPD or LTV, rather than presenting a healthy result.

Individual standalone selectors retain their existing public call signatures and
results; optional private inputs optimize the composed refresh. Independently
called selectors may still load their own evidence. This is not a universal cache
for servicing or future financial posting.

Collateral valuation uses one approved-appraisal query for the loan's items,
selecting the latest effective date/version separately for each item. A local
dictionary reuses the Rates facade lookup once per distinct metal in that call.
The next call reads again. Quote/appraisal identity, date cutoffs, freshness,
custody, policy choice, per-item rounding and missing-evidence behavior are retained.
No original valuation, interest term, financial event or paper-book claim changes.

## Read-only production comparison

On 12 October, a seven-loan cohort covered all three Workspaces: original reviewed
openings, direct native event-fold and recorded-anniversary/3 paper origins, with
one- and two-item examples. Existing and candidate calculations ran in disposable
restricted-role containers against the same live database, in READ ONLY Workspace
transactions. Each container was limited to 0.35 CPU/512 MiB. The candidate overlaid
only the five reviewed files on the exact MR-06 image; neither live container was
restarted or changed.

Before/after source fingerprints matched within each calculation and across the
baseline/candidate pair. Every output fingerprint matched, including exposure,
DPD, collateral evidence, policy identity, completeness flags and risk assessment.
The final frozen candidate repeated the comparison successfully.

| Workspace / profile | Items | Baseline queries | Candidate queries |
|---|---:|---:|---:|
| JCL reviewed opening | 1 | 38 | 26 |
| JCL native event-fold | 1 | 42 | 30 |
| JCL reviewed opening | 2 | 40 | 27 |
| JSK reviewed opening | 1 | 38 | 26 |
| Lakshmi recorded-anniversary/3 | 1 | 91 | 56 |
| Lakshmi recorded-anniversary/3 | 1 | 91 | 56 |
| Lakshmi reviewed opening | 2 | 40 | 26 |
| **Cohort total** | | **380** | **247** |

The composed calculation used **35% fewer queries** over this cohort. Each paper
example used about 38% fewer queries. Source-fingerprint checks and persistence
are additional work outside these calculation counts; this is not a measured 35%
improvement for the entire worker or site.

Final paired calculation timings totalled 1.267 seconds before and 0.834 seconds
after. They exclude process startup and projection writes, and depend on cache,
concurrent worker/database load and sample shape. They are useful supporting
evidence, not a foreground p95/p99, daily catch-up SLA or launch-scale benchmark.

## Regression and scope evidence

- All 79 broader checks and 25 final affected checks passed. The runs overlap;
  80 distinct cases were covered, including the added book-error regression.
- Private-input parity covers native legacy, shared native monthly, recorded paper
  and reviewed opening positions. Tests retain anniversary dates, opening cutover,
  original grace and read-only source facts; no historical position is certified
  as a captured earlier assessment.
- A ten-item/two-metal loan performs two quote lookups and one appraisal query.
  A later quote is visible on a later call; a future appraisal is excluded before
  its effective date and selected on the applicable date.
- Prepared inputs for another loan, date, Workspace or unset context are refused
  without source queries. Existing restricted-role/competing-worker/source-change,
  concurrent-closure, financial-integrity, genuine recovery, valuation-policy and
  non-today live-write tests pass.
- Frozen model/migration consistency, supported-app import boundaries and patch
  whitespace checks pass. All five comparison files match the final checkout.
  The disposable local test database was removed after each run.

The five runtime changes are exposure, delinquency, risk and collateral valuation
selectors, plus the existing risk snapshot service. Pending portability, Party,
dashboard batching and their migrations remain separate. Server comparison proof
is retained under `mr07-20261012` in the existing deployment root. During these pre-release comparisons, no production settings, credentials,
source financial rows, policy choice or image was changed.

## History and pre-release production status

No demonstrated requirement in this slice needs a full immutable assessment-history
table. Existing source evidence, risk transition events and the current projection
remain the supported model. Dated selectors restate available source knowledge;
they do not reconstruct exactly what staff knew or saw in a past assessment.
Add full captured assessment history only for a concrete audit/reporting need.

Before this release, production remained on MR-06. At 02:38 IST on 12 October its worker had completed
573 turns with zero errors: JCL 1,922/2,637 current, JSK 1,601/1,601 current and
Lakshmi 1,922/2,515 current. JSK had no stale/unassessed financial calculations,
but 1,430 unknown valuations and 1,435 provisional book positions still made totals
incomplete. These are dated progress figures, not final coverage certification.

MR-07 implementation and validation completed before the controlled release below.
The seven-loan comparison does not justify changing worker capacity or silently
selecting metal-only valuation. Full launch-scale acceptance remains
[FW-004](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).

## Controlled production release

The release completed at **12 October 2026 03:08:54 IST** (2026-10-11 21:38:54 UTC). Production web and
monitoring worker share `rokkad:monitoring-mr07-20261012-25610cd8b33a`, immutable image
`sha256:d5842197af3e2bec7e812d14f2e317afe1462d84605ee884641d47a76c6b7d0f`. The manifest delta is
`25610cd8b33a7db67862a05825ff0de2d8639f01e4829983f1110f240011f4d9`, with source parent
`6dc71e4a673751aaa19a658a9f326b9ba2427864`. That parent identifies the checkout ancestry;
it does not claim that the dirty checkout was committed or deployed wholesale.
Only the five tested runtime files overlay MR-06; unrelated portability, Party,
dashboard work and migrations remain excluded. No database migration was applied.

Release gates passed:

- A checksum-verified pre-release snapshot restored 202 tables/933,888 rows into
  the explicitly isolated MR-07 database. Native direct/paper/health readers, closed
  browsing, restricted isolation, owner preflight and schema consistency passed.
  Financial source rows and agreements remained identical after worker execution.
- MR-06 restricted startup and native readers passed on that same schema. The
  resource-limited candidate pilot processed explicit JCL/JSK/Lakshmi turns with
  zero errors; graceful shutdown took 1.405 seconds
  with exit code zero. Summary-read measurements remain narrow pilot evidence.
- The exact candidate image was encrypted off-server, downloaded, independently
  decrypted and loaded with matching identity. The recovery key stayed on this
  computer; transient decrypted application-image files were removed.
- The pre-switch backup was `production-20261011T212219Z.dump`, SHA-256
  `ece287e5ebdbaeda82661da29723417f5991d749b4b2c4d566982c361a00d832`. The post-switch backup was
  `production-20261011T213919Z.dump`, SHA-256 `157d57f9abee0c5a4207e277ac655b8c4be1e735f9be81d2b38afcaebf37995f`.
  Both completed with actual remote-byte/retention verification. The post-switch
  check initially warned below its 8-GiB capacity threshold while the disposable
  rehearsal was present. Cleanup restored about 9 GiB; a fresh remote-byte and
  capacity check passed without expiry actions or a low-space warning. Existing
  owner key-custody acceptance remained unchanged.
- The prior worker stopped cleanly before the coordinated image switch. Web and
  worker environment values, commands, mounts and worker caps stayed identical.
  Protected settings/credential hashes stayed unchanged. Both now run the exact
  candidate; all five file hashes match in each container.
- The switch took 13.693 seconds. Sampled HTTPS
  unavailability had an observed upper bound of
  11.180 seconds. HTTPS and
  native/closed readers recovered; all six existing timers resumed. No operator
  financial event or borrower notification was generated.

At final verification the new worker had completed 3 turns
with zero errors and both containers had zero restarts. Current assessments were
JCL 2,637/2,637, JSK 1,601/1,601, Lakshmi 2,515/2,515. Representative active RA00500, C07557, D01622 and D01623 remained
financially supported; JSK 06716 remained closed and readable. Unknown valuations
and provisional books remained explicit, so a current assessment still does not
certify complete economic coverage. No valuation-policy reassignment occurred.

MR-06 had completed catch-up before this switch. The first MR-07 turns were empty
because retained same-contract projections were already current; their short
duration is not processing-throughput evidence. The isolated pilot deliberately
invalidated only 90 derivative rows in its disposable database and processed
actual ten-loan turns (1.730-3.382 seconds) without financial-source changes.
Production was not unnecessarily invalidated or replayed.

The isolated database/dump and duplicate encrypted staging image were removed
after successful release evidence capture. Retained backup objects and the live
database were unchanged by cleanup; free disk was 8.991 GiB.
Server proofs remain in `mr07-release-20261012` under the established deployment
root; safe local release evidence is retained in the matching ignored folder.

MR-07 and the selected combined correction sequence are released. If rollback is
needed, stop monitoring and restore the rehearsed MR-06 web/worker image pair,
which uses the same schema and assessment contract. Do not restore an older
database over later transactions. Full capacity acceptance and the newer setup
export profile remain the separately tracked future work.
