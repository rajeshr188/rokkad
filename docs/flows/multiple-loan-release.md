---
status: active
owner: project
updated: 2026-09-09
tags: [loans, releases, operator-guide]
---

# Release multiple loans

Open **Loans** or **Releases → Release multiple loans**. Search official loan numbers,
borrower names or phone numbers. Select up to 20 active loans with outstanding
collateral in the current business. Different borrowers and licenses are supported.
Selection uses Select2 with a paginated authorized endpoint; no Redis widget cache is
needed. HTMX refreshes the review as loans are added or removed.

Review each loan's principal, interest, fees, exact settlement and collateral photos/
identifiers. An active loan can still be blocked by incomplete accruals, financial
integrity, physical verification or custody rules. Resolve the stated blocker, or
remove the loan. No full batch total is presented while a selected loan is blocked.

For each loan, select its borrower or another collector. For another collector, enter
their name, relationship and how their authority to collect was confirmed. Confirm
the collector is verified and all items are ready for handover. This is an operator
attestation, not automatic proof that a relationship grants collection authority.
Different people may collect their own loans during the same batch.

Enter the payer and optional payment reference. Confirm collection of the exact
combined settlement and choose **Complete selected releases**. The application
rechecks everything; no loan completes if another selected release fails. A changed
or expired quote requires reviewing the refreshed amounts and confirming again.
Repeated identical submissions return the original batch. No separate repayment is
created for money already included in the release settlements.

Batch history shows the original recorded amount, payer and collector for each loan,
with links to individual release details and receipt PDFs. Receipts include only the
collector for their own release. Existing custom layouts can use `release.batch_id`,
`release.paid_by`, `release.collector_name`, `release.collector_relationship` and
`release.collection_authorization`; published layouts are not modified automatically.
Later individual reversals are labelled in the batch without rewriting its history.

If someone will collect later, remove that loan and handle it separately. This workflow
does not introduce deferred collection, partial collateral release, renewal or automatic
notifications. Users without loan.release can view existing records when they have
data.view, but cannot search for or complete a new release batch.
