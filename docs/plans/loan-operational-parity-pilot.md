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

### OP2 Collateral Identity, Media, And Labels

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

### OP3 Hierarchical Storage

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

### OP4 Physical Verification

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

### OP5 Notices

- Audit current Notify v2 coverage before adding new paths.
- Required intents include repayment, interest due, overdue, release,
  regulatory expiry, and verification discrepancy where confirmed.
- Delivery is idempotent and remains separate from loan-domain truth.

### OP6 Reports, Statements, And Regulatory Documents

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
3. Deliver OP2 identity/media/labels. Next.
4. Deliver OP3 hierarchical storage.
5. Deliver OP4 physical verification.
6. Close OP5 notice gaps and OP6 report/document gaps.
7. Run the parity pilot.
8. Add selected bulk actions after their single commands prove stable.

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
