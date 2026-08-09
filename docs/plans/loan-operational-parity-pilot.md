---
status: active
owner: project
updated: 2026-08-08
tags: [girvi, loans, parity, operations, pilot]
related: [../adr/2026-08-08-temporary-girvi-loans-coexistence-and-parity-selection.md, ../apps/loans/architecture-and-girvi-parity.md, loans-girvi-consolidation-fit-gap.md]
---

# Loan Operational Parity Pilot

## Objective

Bring Loans to the required Girvi operational capability, run the same real
operator scenarios in both products, and select the application with the
clearest complete domain workflow. Coexistence remains temporary until a later
retirement ADR.

## Non-Negotiable Boundary

- Girvi owns Girvi records. Loans owns Loans records.
- No record transfer, synchronization, mirroring, or dual write.
- No operational workflow bypasses tenant checks, immutable evidence, custody
  history, correction order, or configured accounting delivery.
- Non-financial operations do not create accounting events merely for audit.
  They use their own immutable operational evidence.

## Pilot Blockers

### OP1 Regulatory Operations — Completed 2026-08-08

- Versioned license documents.
- License renewal history, authority, dates, notes, and supporting evidence.
- Expiry dashboard and notices.
- Expiry blocks new origination while existing records remain serviceable.

Result: `LoanLicense` remains the current setup projection while immutable
issue, amendment, and renewal revisions preserve legal fields and validated,
hashed supporting documents. New UI creation and renewal require evidence;
legacy backfills surface missing evidence without fabrication. PawnLoans freeze
the exact revision used at draft and PostgreSQL prevents post-draft changes.
Owner setup exposes revision history, secure downloads, expiry/document
readiness, and a selector-backed license-register PDF. Existing expiry rules
continue to block new origination. External expiry delivery is retained for the
OP5 Notify v2 audit rather than duplicated here.

### OP2 Collateral Identity, Media, And Labels — Completed 2026-08-09

- Stable workspace-scoped collateral identifier.
- Source-linked photographs and attachment metadata are mandatory during draft
  capture. A draft cannot advance to approval without the required photo
  evidence.
- Every collateral item requires at least one photograph. Draft users may add
  one or more photographs before approval; approval freezes the evidence used
  by the contract.
- After approval, staff may append new photographs for later evidence. Existing
  photographs are never replaced or deleted; each attachment retains actor,
  capture time, and workflow source.
- Appraisal linkage without treating a mutable gallery as valuation evidence.
- The MVP label contains loan number, item identifier, item description, Party,
  weight, and a QR code. Label preview, print, and reprint are audited.
- Scanning the QR code opens the owning loan detail by default. Release,
  physical-verification, and storage-transfer screens may consume the same scan
  to select the labelled item inside that workflow.

Result: every collateral row now has immutable UUID identity; draft edits
reconcile existing rows; JPEG/PNG evidence is mandatory for new UI items and
approval fails closed when any item has no photograph. Photo metadata and
content hashes are append-only and frozen into approval snapshots. Retained
renewal items inherit explicit predecessor evidence while added items require a
fresh renewal photograph. Audited preview/print label PDFs contain loan, item,
description, Party, weight, and a QR that opens the tenant-scoped owning loan.

### OP3 Hierarchical Storage — Completed 2026-08-09

- A tenant-scoped location tree supporting branch, vault, cabinet, box, and
  optional slot levels. The hierarchy is required and levels cannot be skipped:
  Branch -> Vault -> Cabinet -> Box -> optional Slot.
- Stable location codes, active/inactive state, and optional capacity rules.
- Immutable placement and transfer evidence with actor, date, source, and
  reason.
- A current-location projection derived from the movement history.
- Every item has exactly one current storage location. A transfer scans both
  the item QR and destination-location QR before the command records movement.
- Only the workspace Owner may perform storage transfers during the pilot.
- Initial placement may happen after loan disbursement. Missing initial
  placement does not block disbursement and must remain visible as awaiting
  storage placement.

Result: services and PostgreSQL enforce Branch → Vault → Cabinet → Box →
optional Slot. Immutable movements drive a guarded current-location projection.
Owner-only placement/transfer accepts Box or Slot, checks capacity, requires
transfer reasons, prints location QR labels, and exposes awaiting placement.
Release/auction remove location; renewal carries retained location and handles
reversal.

### OP4 Physical Verification — Completed 2026-08-09

- A verification session may cover an entire vault or a selected location
  subtree. It freezes the expected collateral and locations in that scope.
- Observations classify items as found, missing, misplaced, or unexpected.
- Discrepancies require reviewed resolution evidence.
- Missing or misplaced collateral blocks release, renewal, repledging, and
  further storage transfer until an administrator records a reasoned
  resolution.
- Resolution may correct custody/location evidence or formally classify an
  item as lost or damaged. It does not silently rewrite the original
  observation or collateral contract.
- Only the workspace Owner may conduct storage transfers and
  physical-verification sessions during the pilot. A dedicated Custodian role
  may receive these permissions after the pilot.
- Lost collateral requires a compensation workflow before the discrepancy can
  be resolved and its operational blockers cleared. Compensation is a cash
  settlement based on current market value, with the final amount agreed by
  negotiation. Required settlement evidence remains to be specified.
- The policy for releasing damaged collateral is deferred and must remain
  visible future work.
- Completed sessions and observations are immutable.

Implementation result: tenant migration `loans.0032` adds immutable sessions,
frozen expectations, observations, and separate resolutions with PostgreSQL
tenant/transition/append-only guards. Owner-only UI supports subtree sessions,
QR-assisted item/location selection, completion, location correction, and
lost-item cash-settlement evidence. Unresolved discrepancies block storage
transfer, release, release-and-renew, and FundingLoan pledge. Damaged collateral
remains deliberately blocked pending its future release policy.

### OP5 Notices — Completed 2026-08-09

- Audit current Notify v2 coverage before adding new paths.
- Required intents include repayment, interest due, overdue, release,
  regulatory expiry, and verification discrepancy where confirmed.
- Delivery is idempotent and remains separate from loan-domain truth.

Audit result: existing PawnLoan intents already cover repayment, interest due,
overdue, release confirmation, and auction. Tenant migration `loans.0033` adds
the two confirmed gaps as immutable operational intents: license expiry and
completed verification discrepancy. They snapshot source and Owner recipient,
reuse Notify v2 for job/delivery state, participate in the tenant scheduler,
and expose source-local create/retry controls. No duplicate provider state is
stored in Loans.

### OP6 Reports, Statements, And Regulatory Documents

Status: **Completed 2026-08-09.** The tenant report surface now projects all
eight required views from the canonical PawnLoan report/balance fold and offers
CSV, XLSX, and PDF formatting without recalculation. The canonical Loans Party
statement includes current positions and immutable transaction history. The
existing six required document families remain source-linked; fixed loan-ticket
recovery now emits signed `Original` and `Duplicate` pages with one verification
identity. Configurable pilot ticket layouts use their existing
Original/Duplicate composition mode. See
[ADR 2026-08-09](../adr/2026-08-09-loans-pilot-report-and-document-boundary.md).

- Broad Girvi report-count parity is not required. The pilot requires these
  reports: active loans, daily disbursals and repayments, interest due, overdue
  loans, releases and renewals, storage inventory, license expiry, and one
  canonical Party statement.
- The pilot requires these forms: loan ticket, repayment receipt, release memo
  or Form H, renewal agreement, notices, and license register.
- Loan tickets and release forms require customer and staff signature fields.
  Loan tickets produce copies labelled `Original` and `Duplicate`; both share
  one document number and verification identity. Other pilot forms do not
  require signature/copy variants unless a later regulatory decision adds them.
- Signatures are currently handwritten on printed documents. The same workflow
  may also capture digital signatures; either method is valid.
- Filtered CSV/Excel/PDF outputs reuse selectors; exports do not recalculate
  balances independently.

## Nice-To-Have After Stable Single Commands

Named bulk actions may include notices, labels, storage transfers, releases,
repayments, document downloads, and exports. A batch records its input, actor,
policy, row outcome, and replay identity. Each row calls the normal command.
Support explicit all-or-nothing or partial-success policy; never provide bulk
delete or mutable financial-history editing.

## Dependencies And Order

1. Confirm exact reports, regulatory documents, media rules, label content, and
   verification discrepancy policy.
2. Deliver OP1 regulatory operations. Completed 2026-08-08.
3. Deliver OP2 identity/media/labels. Completed 2026-08-09.
4. Deliver OP3 hierarchical storage. Completed 2026-08-09.
5. Deliver OP4 physical verification. Completed 2026-08-09.
6. Close OP5 notice gaps. Completed 2026-08-09. Close OP6 report/document gaps. Completed 2026-08-09.
7. Run the parity pilot. Next.
8. Add selected bulk actions after their single commands prove stable.

Pre-pilot document readiness completed 2026-08-09: document integrity now
fails closed when an active configured loan-ticket assignment omits Original
or Duplicate. `jcl1` currently has no active configured ticket assignment and
therefore uses the compliant fixed dual-copy fallback; its document integrity
command reports zero findings. Physical A4/A5 alignment and duplex behavior
still require the operator printer matrix and cannot be certified in software.

## Parity Comparison

Run identical scenarios in Girvi and Loans and record:

- operator steps and completion time;
- clarity of the next valid action;
- setup and error-recovery friction;
- domain terminology and document clarity;
- custody and physical-location correctness;
- audit, correction, and reconciliation evidence;
- permissions and tenant isolation;
- required notice, report, and regulatory output;
- operator errors, workarounds, and support intervention.

Owner comparison gives greatest weight to clear architecture, clear documents,
readable domain workflows, and ease of operation. Feature count alone does not
select the winner.

An application cannot win solely because it has fewer screens or more legacy
features. It must complete the required workflow more clearly without weakening
the project constitution.

## Exit Criteria

- Every pilot blocker passes its acceptance workflow in Loans.
- The fit-gap register has no undecided pilot capability.
- Operators complete the same scenarios in both applications.
- Results and unresolved risks are documented.
- The owner selects the preferred application.
- A separate accepted ADR defines retirement, remaining-record treatment,
  rollback, and destructive cleanup.
