---
status: active
owner: project
updated: 2026-09-12
tags: [loans, portability, operator]
---

# Import complete Loans history

This strict profile cannot represent interest concessions. Export of a loan with
recorded interest lost now reports that a wider profile is required, rather than
dropping the concession or reporting it as cash. Legacy active openings and
limited-evidence released records follow the separate
[first-import plan](../plans/first-legacy-import.md).

1. Import the borrower using Party portability, retaining the source identity.
2. Prepare the original licence revision, matching series and compatible flexible
   product version. Use **Loans setup → Import Loans → Check historical setup**
   when checking source dates and proposed numbers first.
3. Prepare one canonical [JSONL history](../contracts/loan-history-jsonl.md) per loan.
   Upload it in **Import Loans**. Uploading only stages the source values.
4. Choose the destination licence revision, series and product version, then select
   **Validate and preview complete history**. Borrower matching is exact. Financial
   validation runs the complete historical command in a transaction that is rolled
   back, retaining only staging/mapping/preview records. No loan or financial evidence
   is retained from preview, and no notification, official document or live number
   allocation is invoked.
5. Review source events, original number, proposed local number, source/cutover dates,
   state, recorded balances and remaining contractual principal/interest. These two
   balance views can legitimately differ before future contractual interest accrues.
6. Check the explicit confirmation and choose **Commit complete loan history**.
   Approval binds the operator, Workspace, source and destination mapping for one
   hour. Commit repeats authorization and reconciliation under locks and writes the
   entire loan atomically. A late failure writes no partial loan. Generate a fresh
   preview after a stale approval or destination change.
7. A completed attempt links to canonical export; native loan detail also offers
   **Export history JSONL**. Import the Party and required setup in the destination
   before uploading it there. Repeating identical accepted history is a no-op;
   changing accepted source history is a conflict, not an update operation.

Recent attempts remain accessible from the upload page. An unfinished attempt can
be cancelled with explicit confirmation, clearing staged private values. Completed
loan/source evidence is immutable and cannot be erased through cancellation.
An empty recent-history list means no Loans file has been staged in that Workspace.

This route is owner-only and requires current membership, an active Workspace,
data view/import and setup-management grants, plus the relevant loan action grants.
Export additionally requires data export. Existing web commercial/Workspace guards
remain in effect. It is not an offline/archive recovery route.

Restored active loans participate in normal servicing and monitoring selection;
existing monitoring/appraisal readiness rules still apply. Historical claims do not
create fresh valuation verification. Closed loans have zero settlement, complete
custody return and terminated obligations. Importing does not send messages or issue
new official loan documents. The source includes private borrower and loan values;
use the documented cancellation path for an abandoned staged attempt.
