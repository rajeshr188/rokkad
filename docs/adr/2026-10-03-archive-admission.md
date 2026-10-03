---
status: accepted
owner: project
updated: 2026-10-03
tags: [loans, archives, source-identity, paper-entry]
---

# Admit reconciled archive history through ordinary Loans

## Decision

Implement the [accepted unified recording decision](2026-10-02-unified-loan-recording.md)
by reusing `HistoricalLoanImport` as the immutable financial-origin claim. Add an
optional protected one-to-one link to the selected `HistoricalLoanEvidence` snapshot.
The existing Workspace/source-namespace/scoped-source-ID uniqueness, forced RLS,
immutability trigger and Workspace lock also cover this admission. A new insert
guard binds the archive, namespace, source ID, fingerprint and closed recorded
loan. Existing imports retain a null archive link. No new financial ledger/table.

The first supported archive profile is one fully closed anniversary loan with one
collateral group, no renewal, fees or concessions, using the existing paper-history
calculator. The source status CLOSED alone does not qualify. Staff must supply the
original contract, actual payout, all receipts, final collection and actual return
recipient, and identify checked supporting records. Missing digital original prices
and approval records are not admission requirements. Current monitoring selection
remains separate from original approval.

## Reconciliation and identity

Bind every retained snapshot of the underlying source identity to signed review.
Check known normalized loan numbers, dates, original principal, closing balance,
collateral and payment IDs/dates/totals against the entered timeline. Known conflicts
and duplicate payment claims block admission. Unknown fields may be supplied from
explicitly identified supplementary evidence; never infer zero collections or a
closing payment. Staff verify raw source fields and unresolved borrower mapping;
an existing exact Party source mapping must agree with the selected borrower.
Use the legacy schema-scoped source binding already shared by opening and complete
history imports. Oversized/ambiguous identities need explicit reconciliation.

The Workspace lock serializes archive, opening, complete-history and manual paper
admission. The ordinary number guard excludes only snapshots belonging to the
validated source family inside this command. Other archive/operational number and
source-reference conflicts remain blocked. After admission, the shared source claim
prevents another snapshot or import route creating a second financial origin.
Unknown aliases cannot be deduced from arbitrary renamed IDs/numbers: staff still
confirm source identity; no fuzzy borrower/amount matching silently merges loans.

Preview runs the actual recorded-history writer in a rolled-back transaction.
Confirmation reruns it and inserts the source link in one atomic transaction.
A one-hour signed review binds actor, Workspace, source snapshots, complete input,
supporting-source statement, date, numbering and calculated results. Retries return
the existing loan only for the same selected snapshot and facts. Different accepted
facts require correction of the existing loan, never duplicate admission.

## Presentation, evidence and boundaries

Historical detail opens the existing Loans paper-entry form, with known fields
prefilled and transaction kinds explicitly selected. Archive list/detail show the
linked ordinary loan; the ordinary loan links back to original evidence and media.
Archive documents, fingerprints, attachments and source-only exports stay unchanged.
Reports count canonical loan events once; source archives remain evidence, not debt
or additional cash. A closed admitted loan has no current exposure. Recording time
and actual dates remain distinct and no historical payout/return is performed now.

Owner/import/setup authority is required in addition to the ordinary loan actions.
This does not open unrestricted archive conversion. Renewal-chain source admission,
conflicting claims, broader calculation profiles and attachment reassignment are
outside this first slice. Recorded-origin portable financial export and completeness
integration remain UR-06; source archive export is still available. No production
conversion or deployment is implied by local implementation.
