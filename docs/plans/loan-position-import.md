---
status: active
owner: loans
updated: 2026-10-09
tags: [loans, portability, migration, plan]
---

# Ordinary loan import from a known position

Owner-selected implementation follows the
[position-import decision](../adr/2026-10-09-loan-position-import-without-earlier-history.md).
The old source's RELEASED means completed loan, zero debt and all collateral
returned to the borrower. This accepted interpretation applies to the retained
JCL, JSK and Lakshmi source; external adapters need their own declared meaning.

## Ordered delivery

| Slice | Deliverable | Current state |
| --- | --- | --- |
| IP-01 | Document minimal active/closed position contracts and source interpretation; preserve complete-history restoration | Contract and pure source adapter implemented locally; 34 focused checks pass |
| IP-02 | Read-only retained-data inventory: identities, exact Party/register mappings, known fields, duplicates and contradictions; prepare eligible/exception cohorts | Read-only rehearsal complete: 39,196 candidates and 19 date-order exceptions; no admissions |
| IP-03 | Minimal ordinary closed-position admission, optional original terms, shared balances/details/source media and versioned portability; native and active guards retained | Pending IP-02 findings |
| IP-04 | Reviewed, resumable, idempotent eligible batch conversion through the admission service; source evidence retained and existing loans unchanged | Pending tested admission |
| IP-05 | Ordinary browsing and source access; simplify/archive-directory role only after records accounted for; measure and correct search queries | Pending conversion coverage |

See the [IP-01/IP-02 delivery and inventory](../implementation/loan-position-import-ip01-ip02.md).
The 190 earlier owner-closed/zero JCL claims retain unknown closure date and
physical handover, independently of the release-row interpretation.

Do not turn IP-02 into receipt reconstruction for every old loan. Classify known
position and identity, with specific exceptional contradictions. No individual
history review is required merely because payments are unavailable.

## Acceptance

Active imports preserve original dates and the accepted principal/interest/fees,
continuation basis and custody without back-posting missing transactions. Existing
direct and paper workflows, frozen contracts, monitoring and financial results
remain compatible. Closed imports allow missing original calculation terms,
establish zero current debt, preserve supplied details and returned/unknown
custody, and never add invented collections to cash or income reports.

Source identities are scoped to Workspace/namespace/system/source key. No name
matching, cross-Workspace mapping or hash/filename retry may create another loan.
Preserve source number aliases and existing numbering reservations; imports do not
rewind counters or relabel genuine existing financial records. Changed snapshots
and already-admitted origins require conflict review, not overwrite.

Fresh-database tests cover ordinary reads and refusals of operational mutation,
guarded nullable fields, transaction rollback, retry and source conflicts, forced
RLS and raw restricted-role writes, export/reimport and old-profile compatibility.
Read-only production rehearsal counts and manifests must reconcile before live
conversion. Use an owner-only additive migration with a fresh recovery checkpoint;
runtime processes remain restricted. Do not deploy unrelated billing changes.

## Rollback and retained records

Stop new conversion on failure; preserve successful admissions, original source
documents/media and subsequent actions. Resume only unchanged reviewed batches.
Do not delete archived evidence or restore a database checkpoint over later
customer activity. Keep a compatible reader for nullable imported details.

Search correction remains measured work, not a reason to manufacture financial
history or erase source evidence. Related deferred findings are in
[FW-022](future-work.md#fw-022-main-loans-list-search-performance).
