---
status: completed
owner: project
updated: 2026-10-09
tags: [loans, closure, paper, implementation]
---

# Unified closing experience

The owner approved one familiar Close / release loan action, independent of
origination source, plus consistent individual/bulk completed recording and optional
Workspace operating commitments. Existing financial writers and immutable evidence
remain authoritative. Ongoing unrelated billing edits are outside this change.

| Slice | Scope | Acceptance |
|---|---|---|
| CL-01 | One individual close screen with current/completed purpose, standing defaults and legacy-link compatibility. | Current full release and completed recording retain their permissions, dates, balances and retry semantics. |
| CL-02 | Align bulk completed closure with individual evidence options and authorized concessions. | Mixed confirmed/unspecified returns, optional original numbers, exact totals, atomic failure, retries, custody, documents, CSV and portable recovery pass. |
| CL-03 | Apply optional Workspace recording controls consistently; update navigation, guides and operating language. | Unrestricted paper practice remains supported; cutoff/restriction changes are rechecked at commit, administrator exceptions retain reasons, individual and bulk agree. |
| CL-04 | Verify affected servicing, correction, reversal, race and portability regressions. | Existing profiles remain readable, old submissions retain meaning, existing database guards updated only for explicitly bound unknown cash/return; no production financial action. |

Counter batches retain one combined current payment and their 20-loan limit.
Completed batches retain independent settlements, one actual date and 50-loan
limit. Different dates per row, deferred current handover and archive reconstruction
are outside this change. Loan-level Rokkad-only capture remains a completeness
commitment; later paper facts invalidate that claim through existing readers.

Implementation and local verification are authorized. Production rollout requires
the normal concrete release checks; this task does not post customer transactions.

## Delivery and verification

CL-01 through CL-04 are complete locally. One individual screen dispatches existing
current/completed writers. Extended bulk rows share individual completed evidence,
original numbering and concession handling. Old service requests and HTTP retries
without extended fields retain their original profile and fingerprint. A complete
pre-closing book review is carried through reconciled completed settlement, while
an earlier Rokkad-only future-capture commitment is not silently retained.

Migration 0064 changes two existing PostgreSQL guard functions. Only exactly bound
PAPER / recorded-history-closure/1 / PAPER_SETTLEMENT rows may omit payer/collector;
confirmed-return and counter rows retain their checks. Portable restoration applies
the same narrow evidence rule without disabling model/SQL validation or forced RLS.
No new financial table, journal, backfill or production customer posting is involved.

Fictional isolated PostgreSQL QA passes 93 closing checks (142.020 seconds) and
128 additional servicing/portability/coverage checks (124.749 seconds). They cover
current and recorded actions, mixed batches, unknown/later handover, concessions
and privileges, failed-row rollback, original numbers, signed reviews, legacy
retries, owner restrictions, reversals, corrections, concurrent submissions,
restricted-role database guards and connected export/restore. Final receipt and
legacy HTTP assertions are recorded in Status. Django checks, migration drift and
JavaScript syntax checks also pass.

Production receives the coherent change and owner-run migration 0064 on 9 October
at 15:53 IST. Runtime web and compatible workers retain restricted roles; no
automatic retirement/cutoff is enabled. See the [verified release](../implementation/loan-ui-and-servicing-release-20261009.md).
