---
status: active
owner: project
updated: 2026-09-30
tags: [portability, migration, reconciliation, production, audit]
related: [../plans/portability-confidence-and-completion.md]
---

# Legacy import confidence audit — 30 September 2026

**Later repair checkpoint:** the owner-authorized bounded corrections were applied
and deployed on 30 September; see [the repair outcome below](#production-repair-checkpoint).
The audit findings and no-write statements in the original sections below describe
the earlier read-only run, not the later correction deployment.

## Conclusion and scope

The full source/opening/archive reconciliation found **no discrepancy in the
accepted opening balances, imported loan identities, borrower links, original
dates, collateral economics or preserved closed-history documents** across JCL,
JSK and Lakshmi. Every source loan is accounted for exactly once. This is a fresh
audit of the running production database against the sealed final package, rather
than a repetition of the cutover acceptance figures.

This is **not an unrestricted clean-data certification**. There are source-to-screen
and operational-column gaps, an incorrect unused JCL numbering configuration, and
limited attribution for eight later mutable JCL records. Missing historical facts
remain missing. These findings should drive a small repair queue; they do not
justify re-importing the database or asking staff to attest every imported loan.

Statutory work remains paused. No business records, source attestations, numbering
counters, production configuration or saved Form E batches were changed.

## Method and evidence boundary

- Source archive SHA-256:
  `e2c91ded1d56b6391c0a9dc9c72f0392238490c654612ba477a8e002d5de09e6`.
- Sealed package SHA-256:
  `650becbb16bcd44c2cb9af2281eaeb3d5497dda72a546aaa790b2cc125028400`.
  All **45** manifest-covered files verified; database/workspace binding matched.
- Fresh `pg_restore` extraction in an offline container was parsed as inert COPY
  text. No SQL was restored or executed. All three fresh source indexes exactly
  match the package. Preserved source facts were also compared to parsed rows,
  applying only the versioned owner correction ledger where explicitly recorded.
- Deployed image: `rokkad:auctioneer-handover-20260930-bac8e8898a04`.
  Database: `rokkad_production_20260924`; role: `rokkad_prod_runtime`.
  The financial/source run used an enforced **REPEATABLE READ, READ ONLY**
  transaction and verified the role has neither superuser nor BYPASSRLS.
  Cross-workspace and missing-context read checks passed.
- Later native lending and imported-loan servicing were counted separately.
  The older clean-target `verify_package` was not executed against live data.
- Private reports and extracted source text stay on `172.235.9.64` under
  `/home/rokkad/deploy/cutover-20260924/import-confidence-20260930/`, mode 0700.
  Nothing containing borrower records, photographs or database contents was
  downloaded into the OneDrive project. Repository documentation contains only
  aggregate findings and the owner-supplied C04526 example.

Private artifacts are `summary.json`, `findings.jsonl`, `followup-summary.json`,
`followup-findings.jsonl`, `media-summary.json`, `media-findings.jsonl`, and
`exception-classification.json`, with file checksums in `audit-seal.json`.
The temporary copied runtime environment was removed after all audit containers
stopped. No runtime credential copy is needed to retain the audit results.

Audit implementation:
[financial/source audit](../../scripts/audit_import_confidence.py),
[source and mutable-record follow-up](../../scripts/audit_import_confidence_followup.py),
the local `scripts/audit_import_media_confidence.py` media-audit helper.
That historical helper depends on separate storage reconciliation work and remains
outside the scoped Khata/paper-first commit; its findings stay retained locally.
These are operator scripts using deployed application readers, not web features.
Their JSON findings need classification; changed mutable fields are not
automatically migration failures.

## Reconciled imported cohorts

| Workspace | Customers | Opening loans | Closed-history records | Accepted exclusions | Opening principal | Opening interest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| JCL | 5,887 | 2,438 | 26,664 | 2 | ₹4,68,29,278 | ₹49,61,889 |
| JSK | 648 | 1,514 | 3,840 | 1 | ₹10,46,39,195 | ₹98,25,804 |
| Lakshmi | 2,104 | 2,439 | 8,711 | 0 | ₹5,30,88,900 | ₹80,04,356 |
| **Total** | **8,639** | **6,391** | **39,215** | **3** | **₹20,45,57,373** | **₹2,27,92,049** |

Opening fees are zero in all three workspaces. Source aliases, accepted customer,
contact and address fingerprints, parent identities, frozen opening documents and
staging evidence match. Distinct source identities were not merged. Every imported
loan's opening and current canonical balance readers and next-month interest
boundary check completed successfully. Original obligation schedules are retained.
All 39,215 archived documents, hashes, provenance and findings match the package.

At the main audit snapshot, JCL's 2,438 and Lakshmi's 2,439 imported loans remained
active without later financial events. JSK had **1,481 active and 33 closed**
imported loans, with 33 release receipts and five interest-accrual events. Those
events have actor references; subsequent fingerprint verification passed for all
**6,429** imported-loan events. Their presence is expected later activity, not a
reason to restore the original active states or cutover balances.

The snapshot also contains **63 JCL, 43 JSK and one Lakshmi native loans**, counted
separately; this audit does not certify those new loans' entire lifecycle. JSK's
current imported principal is ₹10,13,07,025 and recorded interest ₹96,85,177.
These are canonical **recorded balances**, not a promise of today's final
collection quotation; continuing interest and settlement use their own readers.

## Source evidence versus newer readers

### C04526

Its frozen opening and source records match. The source borrower record is
retained, its linked Party has an address, and its maturity basis is
`RECORDED_TENURE`, not the owner's missing-tenure fallback.

The Form E reader currently uses a native official-ticket/approval snapshot for
borrower/address particulars. Imported openings have no matching native approval,
and the imported branch explicitly sets tenure to `Not recorded`. This explains
why available migration evidence is not surfaced by that reader. A source-era
customer address must still be labelled as such; it is not automatically proof of
the address on the original pawning date.

Its quantity is retained in opening evidence. Gross weight and a dated original
valuation are not established. The existing blanket warning therefore combines
available-but-unsurfaced facts with genuinely missing historical evidence.

### Cohort-wide coverage

- Every one of the **6,391** openings retains a source borrower record.
- **5,780** openings retain recorded tenure; **611** use the documented owner
  missing-maturity rule (JCL 174, JSK 119, Lakshmi 318). These two evidence classes
  must not be presented as equivalent source facts.
- All **6,391** lack an established valuation dated to original pawning. Some
  retain an undated source value; that must not become an approved original
  appraisal or today's metal-price valuation.
- **6,411 collateral quantities** are retained in frozen opening evidence but
  absent from the newer operational `quantity` column: JCL 2,455; JSK 1,514;
  Lakshmi 2,442. The opening writer does not populate that newer field. This is a
  demonstrated mapping/reader gap, not loss of the preserved source counts.
- Complete pre-cutover payment history and statutory ownership/recipient facts
  are not reconstructed by these opening positions. The retained closed archive
  is evidence, not a replayed operational loan ledger.

## Later mutable JCL records

Separately, fresh Party preparation initially flagged four source-inactive
customers whose **accepted package** status is active. They are the borrowers for
RA00554, C07517, RA00575 and C07545, explicitly confirmed outstanding by the owner
during preparation. This is the accepted outstanding-loan interpretation, not a
new unexplained live change. Original source statuses remain in the source
evidence. Keep this decision visible when showing import provenance.

Eight accepted records differ in mutable fields: **one customer status, three
contact-primary flags and four address-default flags**. No customer name, contact
value or address-text difference was found in this comparison. All eight records
have modification timestamps after admission; the Party status has an updated-by
reference. The seven child records have no equivalent per-change actor field.

The inspected object-linked AuditLog records do not establish who changed these
flags or why. Classify them as **later changes with incomplete attribution**, not
corrupted import evidence and not conclusively verified authorized edits. Original
accepted inputs and digests remain intact. Keep a private exception list; do not
overwrite current choices with the source defaults. Improving ordinary Party
change provenance belongs in the bounded follow-up.

## Numbering finding

All 12 source-mapped loan sequences were checked against the original registers
and subsequently used numbers. JSK and Lakshmi match. JCL has one **confirmed
configuration defect**: source unnamed series, mapped to destination series 5,
has the invented prefix `LEGACY6-` and next number **1**, while the source numeric
register reaches **9999**. Both the series and its sequence are active. The source
contains 1,137 loans in this series; **no native loans** have been issued in it.

This is the same class of unnamed-series continuation issue previously corrected
for JSK. It is not evidence that existing loan numbers changed or that duplicate
loans were imported. Do not use this series for new lending until its intended
continuation/retirement is settled. First prepare the narrow correction under the
existing numbering guards: preserve an empty prefix, reserve all historical and
subsequent numeric identifiers, and respect the maximum/exhaustion rule. Do not
blindly set a counter or alter issued documents. No counter was changed by this
audit. Newly created, non-source-mapped series were outside this sequence check.

## Media

| Workspace | Verified imported references | Missing at original source | Application objects checked |
| --- | ---: | ---: | ---: |
| JCL | 11,664 | 3,159 | 11,677 |
| JSK | 4,722 | 455 | 4,971 |
| Lakshmi | 12,036 | 0 | 12,916 |
| **Total** | **28,422** | **3,614** | **29,564** |

Receipt coverage, evidence hashes, source identities, current attachment targets
and deterministic application filenames match. A fresh R2 metadata listing finds
every expected application object with the preserved byte size. Default customer
photos have an additional profile object, explaining the difference between
reference and object counts. No new missing or size-mismatched imported objects
were found.

This is an existence/size and database-evidence audit, **not a fresh content hash
of every R2 image**, and database plus object storage is not an atomic snapshot.
It does not recertify independent archive/recovery prefixes. The 3,614 source
absences remain explicit; do not describe them as newly lost migration files.

## Completion boundaries and next work

1. Correct the unused JCL unnamed-series continuation under existing guards,
   proving that issued numbers and subsequent activity are preserved. The four
   source-status differences are classified above as accepted interpretations.
2. Prepare source-backed quantity/reader corrections with tests that preserve
   frozen evidence and later transactions. Show retained source facts, accepted
   interpretations and unknowns distinctly. Do not bulk-attest Form E entries.
3. Make the small unresolved-change queue understandable and improve attribution
   of subsequent Party edits; no automatic reset to source values.
4. Resume the selected guided-portability work only after this bounded queue has
   a clear disposition. Complete-workspace export/restore remains a separate
   unproved capability, not an outcome of this audit.

No repairs, new business restrictions, deployment, re-import or permanent printing
were performed. This audit confirms preservation within the accepted migration
scope; it cannot verify physical cash, independently prove the original books, or
invent historical facts the source never established.

## Execution notes

The main financial audit completed at **10:34:27 UTC / 16:04:27 IST** on
30 September. Follow-up and media checks used later read-only snapshots; they
must not be represented as one atomic database/storage instant.

The first checker attempt needed support for archive adapter/owner-decision
supplements, which have no source-row hash. The rerun compares such supplements
through exact archived-document/hash equality and compares actual source records
to the source index. A follow-up attempt exited with status 137; the broad joined
query was narrowed to avoid repeating batch metadata, and the completed follow-up
used memory/CPU limits. Failed-attempt logs remain private. The production web
container was confirmed running with zero restarts after that attempt. Neither
attempt could write business data because database transactions were read-only.

Final main, follow-up and media runs completed, with findings reported rather
than suppressed. Operator scripts passed Python syntax checks. No application
feature changed, so this is live audit evidence, not a claim of new application
test coverage or deployment readiness.

## Production repair checkpoint

The owner authorized fixing the demonstrated gaps. Deployed
`rokkad:import-repairs-20260930-fa40fe550478` over the audited image. The six changed
application files were hash-compared against that exact running baseline before
packaging; candidate/deployed hashes and restricted-role checks passed. No schema
migration was needed. A fresh database backup at **11:04:40 UTC** passed
`pg_restore --list` and SHA-256 verification, retained privately on the server.
This was a new backup/catalogue check, not a new full disaster-recovery rehearsal.

Corrections ran from **11:05:27 to 11:10:56 UTC**, under the restricted runtime role
and existing administrator/data-import authority, in bounded transactions:

| Workspace | Audited opening loans | Null quantities restored | Remaining unknown operational quantities in this cohort |
| --- | ---: | ---: | ---: |
| JCL | 2,438 | 2,455 | 0 |
| JSK | 1,514 | 1,514 | 0 |
| Lakshmi | 2,439 | 2,442 | 0 |
| **Total** | **6,391** | **6,411** | **0** |

Every correction requires matching accepted origin/event hashes, exact item
identities and valid quantities, and refuses contradictory non-null values. Each
changed loan has an actor/source-linked audit. Per-loan locks and before/after
invariant hashes covered every loan field, collateral fields other than quantity,
events and issued-document hashes/snapshots. All matched, including later-serviced
loans. The patch does not write media, financial postings, releases or custody.
New opening imports populate the validated quantity directly; replay and failure
rollback are tested. This is a descriptive projection repair, not a re-import.

JCL series 5 now has **empty prefix / next 10000 / width 5 / maximum 10000**. The
operator rechecked sealed source history through 9999, all current numeric loan
identifiers, prefix overlap and absence of native use before composing existing
configuration and reservation services under locks. It did not renumber loans,
change other counters or expand the ceiling. Only 10000 remains in that register;
any future extension/new series is a separate configuration decision.

C04526's retained source borrower/address and recorded tenure now pass through the
working Form E reader. The bounded Data Portability reader uses completed accepted
inputs and exact opening hashes, not mutable current Party details. Source-snapshot
identity is explicitly not proof of pawning-day identity. Missing-maturity owner
assumptions are labelled separately from recorded tenure; original valuations and
other source limitations remain unknown. No source review or permanent batch was
created, and Form E's review gates remain in place.

Native customer status and contact/address primary/default edits now record actor,
object and before/after flags atomically, including demotions/deletions. No contact
value/address text is duplicated in these entries. **The eight older JCL changes
remain incompletely attributed and unchanged.** No historical actor was invented.
The four accepted outstanding-loan status interpretations remain distinct.

**180 tests passed** (154 repair/opening/reader/numbering/Party/Form E tests and 26
Party-child import compatibility tests). Candidate and deployed C04526 reads,
restricted-role checks and pending-migration checks passed. Anonymous HTTPS still
requires login; source hashes, existing mail/storage timer configuration and mail
health were verified after deployment. This was not a second full R2-content audit.

The final enforced-read-only rerun completed at **11:13:10 UTC**: all 6,411
quantities match and **zero** remain to repair. JCL's numeric counter remains
10000. The temporary runtime-credentials copy was removed after the isolated
processes exited. The final repair seal covers 31 private artifacts; its SHA-256
is `f3be8b2e0d78ba3fd7cee18e61feabb319431761cafa6ab082a5207c0ad773e0`.

Private evidence lives in the server's `import-repairs-20260930/`: sealed source
manifest, preflight, backup metadata, apply report, per-loan database audits and
candidate/deployed verification. Sensitive source/backup/runtime files were never
copied into OneDrive. See the
[decision](../adr/2026-09-30-retained-import-particulars-and-quantity-repair.md) and
[bounded operator](../../scripts/repair_import_projections.py). The earlier audit
seal and original findings remain intact. Next is FW-007's guided supported import
journey; complete Workspace export/restore (FW-012) is still unproved work.
