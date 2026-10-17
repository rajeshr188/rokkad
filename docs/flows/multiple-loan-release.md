---
status: active
owner: project
updated: 2026-10-17
tags: [loans, releases, operator-guide]
---

# Release multiple loans

Open **Loans → Close / release loans**, or **Close / release loan** on an active
loan to start with that loan selected. Explicitly choose **Collect payment and
return collateral now** or **Record a settlement already completed**. Origination
source and entry defaults do not choose for you. The same action is prominent in
**Releases**, the single sidebar destination for closing and release history.
Search official loan numbers, borrower names, Party codes or primary phone numbers
in **Search and select loans**, then select a result. Keep typing to add more or
remove a selected loan before review. Select up to 20 active loans with outstanding
collateral in the current business. Different borrowers and licenses are supported.
Selection uses Select2 with a paginated authorized endpoint; no Redis widget cache is
needed. Choose **Continue to review** after selecting or changing loans/mode.

For completed activity, enter the actual settlement date and review up to 50
independent settlements on that date. The date initially stays blank. Check each
record's amount, payer, recipient and confirmed/unspecified handover basis. No
money is collected again; unconfirmed customer handover retains last-known storage
and PAPER_CLOSED. Saved full-month and started-week contracts use the same
ordinary date-aware settlement calculator as current release. Later recorded
activity and other actual blockers still need reconciliation. Single-loan current
release retains its ordinary authorized interest concession. The remaining steps
below describe a current combined payment covering several loans.

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

**All releases** includes standalone and grouped releases, including partial and
reversed records. **Grouped submissions** shows only submissions saved as a group;
a standalone current release does not create a synthetic group. **Help with closing**
opens the staff guide, with owner-only completed-recording controls linked there.
Existing history URLs continue to work.

Grouped history shows the original recorded amount, payer and collector for each loan,
with links to individual release details and receipt PDFs. Receipts include only the
collector for their own release. Existing custom layouts can use `release.batch_id`,
`release.paid_by`, `release.collector_name`, `release.collector_relationship` and
`release.collection_authorization`; published layouts are not modified automatically.
Later individual reversals are labelled in the batch without rewriting its history.

If someone will collect later, remove that loan and handle it separately. This workflow
does not introduce deferred collection, partial collateral release, renewal or automatic
notifications. Users without loan.release can view existing records when they have
data.view, but cannot search for or complete a new release batch.

Batch search, review, confirmation and completion links retain the current Workspace
through named routes. HTMX history restoration returns the full selection page.
