---
status: investigated
owner: loans
updated: 2026-10-09
tags: [loans, search, performance, production]
related: [../adr/2026-10-05-unified-loan-browsing-with-retained-evidence.md]
---

# Loans list search investigation

The owner reports slow main Loans-list search in JCL, JSK and Lakshmi after the
9 October release. This investigation changes no application code, database
configuration, index, customer data or production reader. Temporary private
operator scripts and documentation are the only local additions.

## Production evidence

Use an isolated, non-listening reader of the live image with the same restricted
runtime environment and forced Workspace RLS. All application queries run in
read-only transactions; statement caps bound diagnostic load. Customer rows,
SQL parameters and full query plans remain in the approved private server child
`/home/rokkad/deploy/cutover-20260924/loan-search-20261009/`. Local ignored evidence
is `.tmp/loan-search-20261009/`; it contains timing summaries, not customer exports.
Temporary server-only runtime credential files are deleted after every probe.

Initial HTMX result-fragment timings, excluding browser/network latency:

| Workspace / sample | All records | Ordinary only | Active only |
|---|---:|---:|---:|
| JCL / RA00500 | 20.208 s | 0.777 s | 0.256 s |
| JSK / 06716 | 1.886 s | 0.191 s | 0.129 s |
| Lakshmi / D01623 | 2.204 s | 0.254 s | 0.250 s |

These are individual observations, not percentiles or browser benchmarks. JCL's
first sample includes cold data/template costs; subsequent warmed All-record
requests take about 3.2–4.4 seconds. Active filtering can also change the result
set, so it is not equivalent to ordinary-only search.

Two union queries dominate: exact pagination count and the selected-reference
page. The unified directory combines ordinary loans with unadmitted retained
historical snapshots, searches source document JSON and preserves exact source
identity/snapshot rules. Source evidence counts in the measured plans are 26,664
for JCL, 3,840 for JSK and 8,711 for Lakshmi. Searching an ordinary loan number
still scans those historical documents even when no archive result matches.

EXPLAIN ANALYZE of the paged reference query confirms extensive document reads
and PostgreSQL JIT overhead: 81–85 generated functions, with 0.89–1.19 seconds
spent compiling each sampled query. Temporary `SET LOCAL jit=off` in diagnostic
transactions removes compilation, but document scanning remains. JCL's sampled
page takes 3.510 s with JIT and 2.959 s without; JSK 1.527 / 0.404 s and Lakshmi
1.749 / 0.625 s. Cache/read differences also affect these individual samples.
No persistent JIT setting is changed.

Each fragment executes 58–71 statements. Apart from the two dominant queries,
most statements are short; the view unnecessarily resolves new-loan setup,
standing policies and metal readiness even for a results-only fragment. The
fragment displays recorded principal, not calculated current balances or risk;
interest calculations and monitoring are not the source of this search delay.

## Isolated query experiment

In a separate ephemeral reader, temporarily replace only the selector function
in process memory: find matching archive primary keys first, then constrain the
unchanged identity/admission/snapshot query to those candidates. No production
source is copied or changed. Preserve ordinary filtering and final ordering.
Limit this experiment to at most 500 archive candidates and explicitly reject
larger sets; this is a diagnostic bound, not permission to truncate real results.

| Workspace | Search | Current warmed request | Candidate-first request |
|---|---|---:|---:|
| JCL | Ordinary number | 4.429 s | 1.132 s |
| JCL | Retained number | 3.214 s | 1.005 s |
| JSK | Ordinary number | 1.874 s | 0.289 s |
| JSK | Retained number | 1.912 s | 0.290 s |
| Lakshmi | Ordinary number | 2.110 s | 0.504 s |
| Lakshmi | Retained number | 2.427 s | 0.503 s |

All six result HTML bodies match exactly, including total, ordering and links.
This establishes a promising narrow-query direction; it does not certify broad
names, short prefixes, blank lists, later pages or all source-identity edge cases.

## Recommended next change

1. Preserve unified browsing and implement bounded candidate-first archive search
   with a complete fallback for broad matches. Do not cap or silently omit loans.
   Keep newer-snapshot checks over the full source identity universe, not just
   snapshots matching the search text, and retain admitted/invalid-binding rules.
2. Skip new-loan setup/readiness work for results-only HTMX fragments. Preserve it
   for the full page and keep normal permission/subscription checks.
3. Measure residual JSON-search cost and test narrowly scoped indexes or immutable
   searchable projections on existing evidence. Prove index use under the actual
   restricted role before choosing a migration. Avoid global JIT changes or a new
   search service as the first remedy.
4. Validate ordinary/historical number, customer name, source ID, short prefix,
   no-match, blank page, dates, CLOSED/ACTIVE filters, selected local mappings,
   broad fallback and later-page counts/order. Include revised snapshots whose
   old text alone matches, admitted legacy/unscoped identities, invalid bindings
   and no-context/cross-Workspace isolation. Benchmark all three real cohorts
   without financial writes before a separate production rollout.

Temporary staff workaround: select **Records → Ordinary loans** for current
operational loans, or Active when only outstanding loans are needed. Historical
closed records remain accessible through All records / Historical records;
the workaround is not a replacement for the query correction.
