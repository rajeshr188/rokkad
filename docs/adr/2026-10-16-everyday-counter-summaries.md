---
status: accepted
owner: loans
updated: 2026-10-16
tags: [loans, counter, reporting, navigation]
related: [../plans/everyday-counter-improvements-20261016.md]
---

# Counter summaries preserve financial, evidence and navigation bases

The owner selects the everyday-workflow review's recommended delivery order.
Use the existing shared financial and posting boundaries in the most-used screens.

Active-loan detail and optional directory amounts use get_servicing_position.
Eligible monthly interest is included only when the retained contract supports
collection recognition. Legacy recorded-debt results retain that label; unsupported
amounts remain unavailable. Recorded balance, contractual due and monitoring
exposure keep their separate meanings. A visible summary is never a posting quote
or permission. Payment/release commands still recheck exact amounts and sources.

Prepared financial inputs may be reused only within one calculation/request for
the matching loan, date and active Workspace. Keep existing prepared-input guards,
independent narrower reads where a forecast is unsupported, and writer-side source
checks. No durable financial cache or monitoring currentness change is introduced.
Directory amounts are page-bound and optional for broad browsing, initially shown
for borrower filters and narrow searches. Adding amounts must not fold the entire
matching portfolio merely to render a page.

A positive historical checked-through statement requires the retained admission's
actual confirmed-complete flag. A missing confirmation remains optional assurance,
separate from shared represented-position coverage. Current book assurance is shown
under the existing evidence disclosure; neither wording nor display creates a review.

Today's ordinary-loan activity uses actual effective dates and today's corrected
knowledge. New issues/net proceeds retain the existing activity calculation.
Receipt counts and principal/interest/fee sums include REPAYMENT and RELEASE_RECEIPT,
including loans now closed. Reversals effective by today exclude the original;
future reversals do not. Invalid components or a mismatched retained received total
make all receipt amount totals unavailable while count/evidence failures remain
visible. No partial sum is labelled a complete total. Legacy absent fees retain
the existing zero-fee convention. Renewal offsets, auction recovery and Khata are
excluded and disclosed. Paper source amounts do not certify physical cash; opening
balances, capitalization and carried principal never become receipts. Historical
corrections restate actual-date figures rather than creating new cash movements.

Return context is an allowlisted Workspace-local navigation hint, limited to the
Loans list, Dashboard and overdue work page. Preserve ordinary filter/page values;
strip exports, fragment-only modes, nested returns and unknown controls. Reject
external, malformed, cross-Workspace or unrelated action URLs. Navigation never
changes membership, permissions, RLS context or review bindings. Action success
returns to its ordinary loan/review destination with the validated context attached.

The entry guard warns before losing document edits, without browser storage,
automatic posting or a new draft state. Existing direct drafts and in-page file
retention remain. A compact entered-principal strip is descriptive, not a validated
payout amount. Default dashboard financial sections remain deferred; the new daily
block travels with the existing queue section. Keep complete overdue work on its
existing page and show only a bounded five-loan preview on Dashboard.

No schema, portable profile, frozen agreement or financial calculation contract
changes. Release the compatible application normally; local acceptance alone does
not amend production or select a deployment.
