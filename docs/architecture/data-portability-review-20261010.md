---
status: audit
owner: project
updated: 2026-10-10
tags: [architecture, portability, completeness, fw-007, fw-012]
---

# Data portability: current capability and completion review

## Conclusion and evidence boundary

Rokkad has a sound domain-owned exchange foundation and several working import/
export paths. It does **not yet provide a complete customer-controlled Workspace
export, fresh-Workspace restore and operational continuation experience**. The
largest gaps are staff access to existing restore services, real portfolio size,
configuration/file coverage and whole-package acceptance. A replacement domain or
generic model copier would add risk without resolving those gaps.

This is a code/documentation review at source checkpoint `a1d79883`, after the
owner requested a fresh assessment. No portability code, customer record,
production setting or financial event is changed. Portfolio counts below come
from dated accepted production reports, not a new live query. Existing test and
release evidence is distinguished from current source inspection. The checkpoint
passed 97 combined onboarding/billing regressions; these are not a fresh execution
of the entire portability suite.

## Three different promises

1. **Import another system's known position.** Earlier payments and origination
   history may be unavailable. Accept supported facts and establish an ordinary
   active or closed loan without fabricating that history.
2. **Restore Rokkad's exported loan records.** Preserve the supported history,
   relationships, agreements and files actually present in the export. A complete-
   history claim must reconcile; an opening-position export must disclose the
   unavailable earlier history.
3. **Move or recover an entire business Workspace.** Include its customers,
   configuration, numbering, loans, files and other applicable business records,
   then prove the destination can continue correctly. Partial loan/Party files and
   infrastructure backups do not alone deliver this customer workflow.

The [position-only import decision](../adr/2026-10-09-loan-position-import-without-earlier-history.md)
already corrects the earlier assumption that every imported closed loan needs a
reconstructed transaction history. The [original exchange decision](../adr/2026-09-11-customer-data-portability.md)
and [servicing evidence decision](../adr/2026-10-05-portable-servicing-evidence.md)
remain appropriate: portability handles staging, mapping, identity and packages;
Party and Loans own their mutations and financial validation.

## Implemented capability matrix

| Capability | Implemented behavior | Staff delivery and limits |
| --- | --- | --- |
| Party master and child records | CSV/XLSX/JSONL parsing, reviewed mappings, source identities, normalized comparisons, explicit commit and safe retries; contacts, addresses, identifiers, roles and relationships | Browser workflows exist. Six-profile `party-bundle/1` provides combined review/atomic commit. Maximum 1,000 rows and 5 MiB per profile. |
| External outstanding-loan register | Guided borrower/setup mapping and supported opening-position admission through ordinary Loans | Browser CSV/XLSX template; 20 loans/200 collateral rows per upload. Current adapter requires unchanged principal and first month paid upfront. |
| Complete supported loan history | `loan-history/1` through `/4`, original economic facts, applicable shared servicing contract, receipts/allocations and reconciliation | Browser JSONL staging/review/commit; 5 MiB, at most 20 items/240 events per loan. Unsupported history is rejected. |
| Supported opening-position export/restore | Frozen checkpoint, source identity and supported subsequent servicing; newer profiles carry explicit continuation/boundary facts | Loan download plus operator restore command. This does not make the complete-history upload screen an opening-file restore screen. |
| Connected servicing history and files | `loan-servicing-bundle/1`, supported renewal/release graphs, reversals, auction records, book reviews, photos and issued document bytes; fresh destination IDs and reconciliation | Loan ZIP download and `restore_loan_servicing` operator command. No complete browser restore path. Bound: 20 connected loans, 5,000 rows, 200 files and 32 MiB expanded. |
| Ordinary closed-position admission | Zero debt and explicit returned custody, nullable unavailable original terms, source/media preservation, no invented receipts/payouts | Existing-source batch conversion is implemented and production-verified. Standalone JSON/ZIP preview/admit services exist, but no browser/management-command entry point invokes the file-admission services. |
| Exact native Loans recovery | Frozen model/guard inventory, original IDs, configuration and broader operational rows/files | Offline owner-only operation in an empty Loans area of a matching recovered database. Bound: 50,000 rows/256 MiB. Requires matching Workspace and external prerequisites; not a fresh-Workspace customer transfer. |
| Complete business Workspace package | Desired export/restore/continuation acceptance is documented in FW-012 | Not implemented. Existing partial packages do not include all configuration, apps and files. |

Party bundles explicitly exclude Loans, binary/KYC files, Party metadata, role-type
definitions, Workspace settings/access and other apps. Servicing bundles explicitly
exclude Workspace configuration, Party master, funding, storage and outbound jobs.
They require destination borrower/licence/series/product mappings. Supported source
actor claims remain provenance; they do not create destination user accounts or
permission grants. Restore records the actual destination actor and does not pay
out cash again or resend source notifications.

Complete-history preparation currently maps supported non-amortizing flexible or
bullet products. It is not an arbitrary EMI/amortization importer. After transfer,
source book/capture claims remain evidence; the destination must review its own
future capture/completeness. Current collateral monitoring uses destination
prices/appraisals and available item facts rather than adopting a source risk
result as a new live assessment. Missing evidence remains visible.

### Current evidence of correctness

The [closed-position production conversion](../plans/loan-position-import.md)
and [BS-05 release](../implementation/compact-closed-position-release-20261010.md)
record 39,196 ordinary closed positions with 19 source records held separately.
BS-05 records 112 closed-position regressions, 180 broader compatibility checks
and an isolated database/image recovery rehearsal. Those establish that accepted
closed positions and their protected source evidence are real implemented paths;
they do not establish a complete customer Workspace transfer.

Financial restore services validate mapping, hashes, graph ownership, balances,
custody and idempotency; re-check access and live destination state at commit; and
use guarded Loans writes under forced RLS. Preview is non-posting. Unsupported
graphs/media fail rather than silently degrade the export. Exact offline recovery
uses different authority and must remain inaccessible as an ordinary import path.

## Confirmed completion gaps

### 1. Export and import screens are asymmetric

[export_loan_data](../../apps/tenant_apps/loans/services/opening_export.py) selects
closed JSON/ZIP, servicing ZIP, opening JSONL or history JSONL according to actual
evidence. Photos, issued documents and connected operations commonly select ZIP.
However, the [current loan upload](../../apps/tenant_apps/data_portability/loan_history_views.py)
accepts only complete-history JSONL and calls the history parser. Staff cannot
restore every downloadable profile through that screen.

The servicing operator command is a genuine restore path. Closed-position file
preview/admit services currently have only service/test callers. This is missing
product integration, not evidence that a ZIP export restores incorrectly.

### 2. Some export bounds are below known production volume

[Party export](../../apps/tenant_apps/data_portability/services.py) selects the
whole Workspace and refuses more than 1,000 parties. The Party bundle separately
enforces the same per-profile cap. The [30 September audited populations](../implementation/import-confidence-audit-20260930.md)
were JCL 5,887, JSK 648 and Lakshmi 2,104 customers. JCL and Lakshmi therefore exceed
the existing whole-Party export bound; even JSK's child profiles can independently
exceed their bounds.

The exact native Loans recovery row cap is not a universal escape route. The
accepted JCL cohort has 26,649 ordinary closed positions. Each requires at least a
PawnLoan, its HistoricalLoanImport and its sole accepted opening event: **79,947
rows**, before other retained/operational rows. That derived minimum exceeds the
50,000-row cap. No production export was attempted during this review.

Small bounds are useful safety controls. Completion needs predictable chunking,
consistent snapshot semantics and resumable work, rather than simply removing
limits or loading a large portfolio and all media into memory.

### 3. The spreadsheet adapter is narrower than the domain

The [outstanding-register adapter](../../apps/tenant_apps/data_portability/opening_register.py)
rejects reduced principal. It supports a fixed original-anniversary upfront
interest rule and aggregate rounding rather than every current standing-policy
contract. Its servicing product is already **flexible partial payment**, not a
bullet-only product. That product capability does not remove the source adapter's
unchanged-principal restriction.

Newer opening services support explicit reduced-principal/checkpoint continuation
facts. Extending the adapter should use those existing capabilities with a new
versioned source contract, not reinterpret frozen imports or guess the month's
principal base. A generic closed-register template is also different from the
current source-specific retained-archive conversion.

### 4. Valid operational graphs can still be unportable

[Servicing export](../../apps/tenant_apps/loans/services/servicing_bundle.py)
explicitly blocks origination corrections retaining native source IDs and funding/
storage dependencies outside its inventory. Large connected release/renewal graphs
can exceed the 20-loan bound. Missing/corrupt files also block complete export.
These honest limits must remain visible until reviewed remapping/coverage exists.

### 5. Business configuration and complete file coverage are unfinished

Current customer packages do not collectively restore everything needed for a
fresh business: licences/revisions, series/counters, products, effective economics,
Rates, document layouts, all Party attachments and other applicable business
records. The exact recovery tool includes broader Loans configuration but keeps
native identities and depends on a matching recovered database; it does not close
that gap. See [FW-012](../plans/future-work.md#fw-012-complete-workspace-export-and-guided-restore-into-a-fresh-workspace).

Database/R2 infrastructure recovery is independently accepted. It serves platform
recovery and does not replace a tenant-scoped customer package. Customer package
encryption/key recovery also needs an explicit design; encrypted server backups
do not automatically encrypt downloaded Party/loan files.

### 6. Historical audits need clear current pointers

Earlier portability audits retain useful findings but describe older origination,
closed-archive, release and local-only assumptions. Some are now superseded. Use
this review for current delivery boundaries and the published contracts for each
frozen profile. Do not use an old profile limitation as a universal PawnLoan rule.

## Recommended controlled order

These are proposed next slices, not an implementation or deployment authorization.
Keep them in existing FW-007/FW-012 rather than start a competing portability engine.

1. **Publish one current capability/coverage catalog.** State each profile's
   format, version, limits, exclusions, importer, permissions and acceptance.
   Distinguish position import, complete loan restoration and Workspace transfer.
   Add this matrix to ordinary setup/import guidance.
2. **Connect existing financial restores to one staff import journey.** Classify
   supported files by validated manifest/profile, then route to existing Loans
   services. Provide borrower/setup mapping, non-posting review, exact confirmation,
   financial/file reconciliation and idempotent retry. Support opening, history,
   servicing and closed-position files before claiming download/restore parity.
   Do not auto-execute arbitrary uploaded SQL or weaken admission guards.
3. **Extend essential-position source templates.** Add supported reduced-principal
   active checkpoints and ordinary closed positions, using explicit known/unknown
   facts and custody meaning. Do not require unavailable payments or historical
   quotes merely to record a supported imported position. Continuing active debt
   still needs enough per-item facts and the applicable future interest contract.
   The exact 190-JCL recovery exception stays source/hash-bound and temporary.
4. **Make export/restore work at real portfolio size.** Chunk Party and financial
   inventories/media with a consistent snapshot/manifest and bounded resumable
   jobs using existing staging patterns. Preserve connected relationships, global
   identity maps and numbering across chunks. Prove interrupted retry, conflicting
   changes, missing media and representative JCL/Lakshmi volumes. A short-lived
   reviewed export lock or maintenance window may be simpler than complex live
   snapshot machinery for an initial complete-package release.
5. **Deliver the FW-012 fresh-Workspace package.** Inventory applicable app data
   and configuration, preserve immutable contracts/files, restore dependencies
   and reconcile before exposing the destination for operations. Start with an
   empty compatible destination and manual download/upload. Keep passwords,
   sessions, provider secrets, subscriptions and staff grants out. Source history
   must not silently grant destination lending authority or complete book review.
6. **Expand only demonstrated remaining graph gaps and prove continuation.**
   Address funding/storage/correction dependencies needed by real portfolios,
   with explicit versioned coverage. Verify export → fresh restore → re-export
   semantic equality, balances/custody, anniversary interest/rounding, current
   risk monitoring, exact document bytes, and next-number/new-loan behavior.
   Unknown valuation evidence should remain an honest monitoring gap, never an
   invented historical appraisal or a different loan lifecycle.

The next implementation candidate is the staff restore integration in step 2,
supported by step 1's coverage contract. Complete Workspace portability remains
unaccepted until steps 4–6 prove the actual business continuation scenario.
