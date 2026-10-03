---
status: active
owner: project
updated: 2026-10-02
tags: [portability, migration, reconciliation, fw-007, fw-012]
---

# Import confidence first, then usable data portability

**2 October direction update:** after the audit/repair and bounded guided-import
work below, the owner selected [unified loan recording](unified-loan-recording.md)
for real-time and delayed paper business through ordinary Loans. The accepted
design includes Lakshmi's total-only receipts and conditional admission of
reconciled archive history. Implementation begins with dated receipts on existing
opening loans; see the [local checkpoint](../implementation/unified-loan-recording.md).
Broader history admission remains pending. Missing financial facts and bulk archive
conversion are not inferred from this direction.

## Owner decision and immediate scope

On 30 September the owner paused further statutory-form/document work to establish
that the legacy import is sound, then make data portability robust, understandable
and complete within an explicit supported scope. This is the current priority for
this workstream. Existing deployed statutory features and JCL's E-1 remain intact;
do not create source attestations or permanent print batches to remove warnings.
Do not expand statutory work or start another feature alongside this effort.

The first deliverable is a **three-Workspace import confidence report**, not a new
wizard, re-import or request to manually review every loan. Report JCL, JSK and
Lakshmi separately. Lead with confirmed financial/linkage problems, then source
limitations and presentation gaps. Ask the owner only for specific business facts
that cannot be established from retained evidence.

## What the preliminary review establishes

**30 September delivery update:** the [full read-only audit is complete](../implementation/import-confidence-audit-20260930.md).
All frozen opening/archive cohorts and media receipts reconcile; later JSK closures
are preserved. Move to the bounded repair queue below. The following preliminary
notes remain historical context, not the current completion state.

- The cutover checkpoint records reconciliation of 8,639 customers, 6,391 outstanding
  loans, 39,215 closed-history records and three explicitly accepted unused source
  exclusions. These are import-time figures, not today's active-loan totals.
- Server-side completion metadata was rechecked read-only on 30 September:
  `finalization/completed.json` says `MIGRATION_AND_LOCAL_RECOVERY_VERIFIED`;
  `run/completed.json` says `RECONCILED_DATABASE_ONLY`; `run/source-check.json`
  records an exact snapshot with no new preparation required. The bound package is
  `650becbb16bcd44c2cb9af2281eaeb3d5497dda72a546aaa790b2cc125028400` in
  `rokkad_production_20260924`. This confirms retained acceptance evidence exists;
  it is not a fresh whole-portfolio reconciliation.
- The final media checkpoint records 28,422 verified attached references and 3,614
  missing source files. Check their documented classifications; do not present
  missing-at-source files as newly lost media, or claim complete photo recovery.
- C04526's Form E projection has no hard mapping blocker but lacks a separate
  Form E review. The print reader reports missing/partial original identity,
  tenure, collateral particulars, valuation and ownership evidence. It currently
  obtains original borrower/address particulars from native official-ticket
  snapshots; imported openings take a different evidence path. Therefore the
  warning is not proof that these data were absent from the legacy dump or lost
  during import. Trace the actual fields before classifying the problem.
- Older portability plans contain historical rehearsal instructions under headings
  that can look current. This plan and current Status take precedence; preserve
  older evidence without repeating obsolete next steps.

## 1. Audit the existing import without changing business records

Use the final frozen September 24 source and sealed package, not an earlier
rehearsal and not today's possibly changed legacy application. Verify their
identity/checksums. Keep customer-level reports, source files and backups private
on the server; repository documentation gets aggregate findings and references.

Account for every source loan exactly once: admitted opening, retained closed
history, or explicitly accepted exclusion. Check stable source/destination identity,
borrower relationships, licence/series, complete loan numbers and duplicates.
Reconcile frozen opening principal, interest, fees, original dates, continuation
rules and collateral/custody with the accepted package and owner decisions.
Check contacts/addresses and media linkage, then source facts needed by exports
and reports. Sample boundary cases in addition to full identity/amount comparisons.

Trace C04526 as the first field-level example:
**frozen source → prepared record → accepted import evidence → destination → reader**.
For each field distinguish what the old system actually said, any approved
interpretation/transformation, what is preserved now, and what the screen reads.
Apply the resulting checks across the cohort; do not extrapolate one example into
a claim that every loan is correct or defective.

The new application has real post-cutover lending, collections, releases,
reversals and edits. Separate unchanged import evidence from later authorized
events. Derive current balances using canonical readers; never expect today's
balances or total rows to equal cutover totals. The old `verify_package` command
asserts a clean just-imported target (including exact Party/loan/event counts and
mutable profile equality). **Do not use it unchanged to judge live data:** legitimate
post-cutover activity would appear as a mismatch. Reuse its pure comparisons in
an audit that understands later changes; do not run replay/commit.

Classify findings in plain language:

| Result | Meaning | Response |
| --- | --- | --- |
| Matched | Source/accepted interpretation and destination agree | No repeat owner review |
| Expected later change | Traceable activity after the cutover | Preserve and explain |
| Missing at source | The old system did not establish the fact | Retain unknown; request a fact only if necessary |
| Retained but not surfaced | Evidence exists but the reader does not use it | Correct mapping/display with provenance |
| Approved interpretation | A documented owner rule resolves a source ambiguity | Show its origin; do not label it raw source fact |
| Actual mismatch or unexplained change | Expected identity/value/link does not reconcile | Investigate and prepare a specific correction |
| Unsupported history | Source evidence is retained but cannot support an operational reconstruction | Explain coverage; do not fabricate events |

**Exit:** a branch-by-branch report with checked counts/totals, coverage, exception
counts/examples, evidence pointers and remaining uncertainties. It must say which
checks passed and which did not run. A failed new statutory projection must not
silently become a migration failure or a new lending restriction.

## 2. Correct only demonstrated problems

### Repair queue selected after the 30 September audit

**Delivered 30 September:** the following queue has its disposition in production.
JCL series 5 is numeric/next 10000 with its existing 10000 ceiling; all 6,411
quantities are restored with audits and preservation checks. Retained source
identity/address/recorded tenure are surfaced with provenance. Future native Party
status/default changes have actor and before/after audit. The eight older changes
remain unchanged and incompletely attributed; source limitations stay explicit.
180 tests passed. See the [repair checkpoint](../implementation/import-confidence-audit-20260930.md#production-repair-checkpoint).
The numbered list below preserves the selected scope, not outstanding repairs.

1. **Numbering:** fix JCL's unused unnamed series 5, currently active with
   `LEGACY6-`/next 1 while the source numeric register reaches 9999. Recheck no new
   native use, all existing identifiers, prefix constraints and exhaustion under
   existing domain guards immediately before any correction. Never rewind a counter.
2. **Retained source facts:** 6,411 collateral quantities exist in frozen openings
   but not the newer operational column. Design the smallest source-backed
   mapping/reader correction and prove existing servicing/documents are preserved.
   Surface source-era borrower/address and recorded-versus-interpreted tenure with
   provenance. Do not resume statutory print/attestation work as part of this fix.
3. **Mutable Party provenance:** keep a small private queue for one JCL status,
   three contact-primary and four address-default changes after import. Timestamps
   alone do not prove authorization; current evidence lacks complete attribution.
   Preserve current choices, improve future actor/reason tracing, and ask for a
   specific business decision only if a correction requires it.

The four source-inactive/accepted-active borrowers correspond to the owner's
outstanding-loan decisions and are classified as accepted interpretations, not
new import defects. Missing dated original valuations and 3,614 absent source
files remain honest coverage limitations. No remediation was performed by the audit.

Reuse preserved facts before asking staff to re-enter them. Fix faulty readers
without changing valid source evidence. For genuine import defects, prepare
targeted, source-backed repairs and demonstrate that subsequent transactions are
preserved. Use existing domain services, compensating events or append-only
evidence as appropriate. Never overwrite posted history, reset balances/counters,
silently merge customers or re-import the dump into the live database.

Unknown facts remain unknown. Review only the exceptions requiring a business
decision; an acknowledgement is not verification of an undocumented fact.
Prove repair behavior in isolation, then rerun affected reconciliation. Preserve
the original source and correction audit. Statutory work remains paused here.

## 3. Make the supported import journey understandable (FW-007)

**30 September implementation:** the [guided outstanding-register flow](../flows/guided-outstanding-register-import.md) adds XLSX/CSV upload, customer matching, reviewed totals/terms and atomic confirmation over the existing opening engine. Its first rule requires unchanged principal and first-month-upfront original-anniversary interest. Additional rules, vendor mappings and manual paper entry remain future work; FW-007 is partial. See Status for deployment and test evidence.

Reuse existing private staging, Party mapping/presets, complete-history admission,
reviewed openings, closed archives, media pipeline and idempotent commits. Select
one documented loan spreadsheet/manual-entry profile before widening input support.
The normal new-loan form must not simulate a new payout for an old loan.

The user journey is: choose supported input → map/match borrowers and licence/series
→ preview and see coverage → resolve actual exceptions → approve → import safely
→ view results and reconciliation. Explain missing versus zero, historical versus
operational records, original dates/interest, handover date and protected numbering.
Group repeated issues; do not require repetitive per-row confirmations of facts
already accepted and unchanged. Preserve permissions, RLS, stale-review protection,
safe retry and no-side-effect previews. A representative user must finish the
supported journey without hand-written JSON or shell commands.

## 4. Prove export and recovery coverage, then complete the package (FW-012)

First inventory what existing exports preserve and test their supported restore
contracts in an isolated empty Workspace. Reconcile identities, money, historical
coverage, attachments and configuration; record unsupported features explicitly.
Current per-loan/Party support must not be advertised as a complete Workspace
backup. Complete Workspace packaging and restore follows a bounded coverage design
in FW-012, using existing services rather than a second importer. No live workspace
switch, backup upload destination or activation of a restored copy is implied.

## Meaning of completion

The selected release is complete when the existing migration has an intelligible
reconciliation report, demonstrated defects are resolved, genuine unknowns are
visible, the supported customer migration journey is usable, and export/restore
preserves its advertised coverage with repeatable tests. “Any Excel/database with
no review,” invented missing history, and unrestricted restoration over a running
Workspace are not completion criteria.

Deliver one checkpoint at a time. **The audit and demonstrated corrections are
complete; the first guided outstanding-register journey is implemented. Review
its bounded source profile with a representative owner before widening coverage.** Keep the older attribution exceptions and genuine
source gaps visible. Resume Form E only when the owner chooses to return to
statutory work.
