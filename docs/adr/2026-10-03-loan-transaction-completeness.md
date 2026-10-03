---
status: accepted
owner: project
updated: 2026-10-03
tags: [loans, paper-entry, monitoring, notices]
---

# Explicit transaction coverage for monitoring and reminders

## Decision

Continue the [unified recording decision](2026-10-02-unified-loan-recording.md)
with an append-only LoanTransactionReview belonging directly to one Workspace and
loan. It records the checked-through business date, whether activity is complete
or unresolved, the paper reference/reason, present reviewer/time, a request key and
a fingerprint of the financial events and loan state reviewed. It neither posts
money nor asserts an original digital lending approval. No attachment is required.
Migration 0043 adds forced RLS, parent-scope and immutability guards and registry
coverage. Prior confirmations survive later corrections or withdrawal.

Ordinary loan detail opens a preview/confirm form. Confirmation requires data.edit,
current Workspace write access and a one-hour signed review bound to actor,
Workspace, loan, submitted facts, current activity and previous review. Confirmation
locks the loan; exact retries return the existing row. Concurrent different reviews
cannot both supersede the same predecessor. Interactive review is bounded to 1,000
financial events. Staff can report missing activity or move the checked date back.

New paper timeline admissions record their initial confirmation in the same atomic
transaction for every admitted member. Existing recorded origins without this row
need an explicit review; migration does not fabricate a present confirmation.
Opening loans require confirmation from their opening checkpoint onward, retaining
the checkpoint's limitations about earlier history. Ordinary system loans retain
their existing interpretation unless staff explicitly assign a paper review.

## Date and source semantics

A date of today means paper activity checked up to the review, not a prediction
that no more paper business will occur today. Every subsequently entered financial
event, including an accrual or correction, invalidates the source binding. Staff
must check again before relying on it for reminders. Date rollover makes an active
loan's earlier confirmation provisional. A closed loan does not become incomplete
merely with time: coverage must reach its final activity. Review never changes
the original admission cutoff or the actual transaction dates.

This is a conservative per-loan rule. It cannot detect an unentered receipt that
staff have not disclosed. Explicit staff confirmation remains the source of paper
coverage; the latest digital payment and Workspace-wide status are not substitutes.

## Monitoring and reports

Calculate current debt and collateral risk from the existing canonical records even
when paper coverage is incomplete. Add a visible provisional explanation and retain
coverage separately from price/appraisal freshness. Snapshot contract V4 includes
transaction review provenance; older snapshots need reassessment. The dashboard and
portfolio withhold definitive totals if any assessed loan has incomplete transaction
coverage. Individual calculated values remain inspectable, and closed loans remain
outside current exposure.

Active/interest/overdue reports and borrower statements expose transaction status
and checked-through date, including CSV, XLSX and PDF. Existing correction rows
remain restatements, not additional cash. Scope/source links and archive accounting
semantics remain unchanged.

## Borrower reminders

Enable reviewed repayment and overdue reminders for covered paper/opening loans
through the existing risk-notice preview/confirm workflow. Consent, supported
channel/provider, templates, quiet hours and current risk assessment still apply.
Use anniversary collection interest for admitted paper contracts and supported
opening continuation interest for opening loans. Admission/review alone creates no
notification intent and performs no historical sending.

Each such notice freezes and references its transaction review. Migration 0044
retains native notice deduplication and adds uniqueness per risk event, channel,
template version and paper review. An obsolete intent remains retained; after a new
review staff can prepare a new intent instead of editing the old message.

Notify's common provider boundary rechecks the active Workspace, latest review,
unchanged financial source, current-day amount, active loan/open alert, current
assessment, consent, provider and quiet hours. Hold the loan lock through the
provider attempt and reload job state so concurrent workers cannot resend an
already sent paper notice. Failed checks record a delivery failure without calling
the provider. Loans owns these checks; Notify continues to own delivery state.

## Delivery boundary

This is UR-06's completeness, monitoring, report and reminder slice. Full recorded
contract/schedule documents, restorable recorded-origin portability and subsequent
renewal/auction recovery integration are still separate remaining UR-06 work. The
existing guards for those unsupported operations remain explicit. Review confirmation
must never be treated as authorization to bypass them. See the
[delivery plan](../plans/unified-loan-recording.md) and
[implementation evidence](../implementation/unified-loan-recording.md).
