---
status: active
owner: project
updated: 2026-09-30
tags: [fw-013, statutory, loans, notices]
---

# Statutory forms and manual notice service

**Paused for further delivery, 30 September:** the owner wants confidence in the
legacy import and a usable data-portability workflow before continuing statutory
forms. Preserve delivered functionality and JCL E-1; do not proceed with source
attestations, permanent pages, revised review gates or another form increment.
The [portability confidence plan](portability-confidence-and-completion.md) is the
current priority. Existing operational safeguards remain unchanged.

The owner selected the full scenario-based statutory-document capability, with the
auction notice/readiness gap as the immediate implementation priority. Preserve the
Form E print-page/manual-annotation decisions in [FW-013](future-work.md#fw-013-tamil-nadu-prescribed-forms-and-pledge-book-in-englishtamil).
Digital borrower reminders are an independent channel workflow.

## Delivery scope and evidence

The first increment, deployed on 30 September after owner acceptance, implements the selected auction postal handling
path: reviewed catalogue PDF, exact reprint, printing record, postal article/date/
receipt, acknowledgement/POD, return/referral/officer-receipt/certificate handling,
readiness review, withdrawal and start/completion gates. Workspace users can find
the scope guide through Reports; administrators find the workflow on each auction.
An administrator's recorded review is not a professional certification.

Deployment preflight confirmed no open auctions across all six Workspaces. Private
backup, migration, restricted-runtime and live page checks passed; see Status.
The owner accepted cosmetic layout changes as follow-up work. The auctioneer
prepares the actual notices; branch staff post and track them, then reconcile
unreleased loans before returning the auction list. The consolidated administrative
handover increment now preserves fixed cohorts and reviewed versions with printable
lists/CSV, release/repayment/custody reconciliation, explicit remaining selection,
stale-review rejection and per-loan readiness links. See the
[handover guide](../flows/auctioneer-handover.md) and Status for validation/rollout.
Attach actual signed notices to the per-loan evidence. A handover is not the
prescribed multi-pledge auction catalogue.

The current template is a single-pledge Rule 12 catalogue extract for its loan's
auction attempt. Multi-pledge auction catalogues and a reviewed Tamil heading/
statutory wording set remain necessary extensions before claiming the entire
auction document suite. Source particulars including Tamil text are preserved;
signatures are left for the responsible person. No authority certificate is generated.

The source reviewed is the [CRA published Rules](https://www.cra.tn.gov.in/tnscs/Files/act/003b_Tamil%20Nadu%20Pawnbrokers%20Rules%201943.pdf),
especially Rules 6, 7, 11 and 12 and the appended forms. Current consolidation and
local directions are not independently certified. Require a recorded current-rule
review reference and actual supporting evidence before readiness approval.

## Remaining scenario inventory

| Scenario | Prescribed output | Next delivery/acceptance |
| --- | --- | --- |
| Licensing | A; B is issued by the authority | Application preparation and attachment inventory; do not issue B |
| Transfer, agent, lost-ticket and ownership circumstances | C, D, D-1 through D-8 | Exact trigger/recipient/signature matrix, reviewed templates, appropriate service path |
| Daily pledges | E | Deployed register, both A4 layouts, source review, permanent full/partial batches, exact reprints and daily annotation aid; branch book opening and coverage limits remain |
| New pledge | F | Reconcile existing custom tickets with prescribed wording and language |
| Sale/redemption | G/H | Map native and imported evidence; include actual recipient and sale particulars |
| Account copy, certification and pass-book | I/J/K, Rule 11 | Generator, actual certification and requested-statement service evidence |
| Auction notices | Rule 12 | First increment deployed; multi-pledge catalogue and reviewed Tamil wording remain |
| Auctioneer register | L | Support responsible auctioneer records, not invented lender attestations |
| Periodic advances | M | Reviewed period definitions and reconciled return |
| Surplus after auction | Rule 12(14) | Surplus settlement support first, then intimation and postal evidence; current exact-debt-only recovery still fails closed |

Authority permits, publications, officer attendance and official service certificates
are externally performed facts to capture, not documents the app can fabricate.

## Validation and rollout

- Tests exercise both service routes, late/future dates, duplicate requests,
  immutable database evidence, restricted-role RLS, private/authorized downloads,
  digital-SENT bypass rejection and existing loan recovery/reversal behavior.
- Visually inspect one-page and overflowing fictional PDFs, including Tamil
  particulars; obtain physical-paper and responsible auctioneer review before use.
- Apply `loans.0029_statutory_notices` through owner-only migration settings, refresh
  restricted runtime grants, and verify both forced-RLS tables and private storage.
  Rebuild storage inventory/cleanup tooling with both new FileField references.
- Existing initiated/in-progress auctions require the new notice evidence; do not
  synthesize historical service or grant readiness because old Notify jobs say SENT.
  Inspect those records read-only and coordinate their handling before deployment.
- Deployment completed on 30 September after backup and candidate/live checks;
  the new schema is present with restricted runtime permissions and forced RLS.
  No real recipient contact occurred. Keep future candidate journeys fictional.
- An operational rollback must preserve new evidence and files. Do not reverse the
  migration after real evidence exists or restore the unsafe SENT-only auction gate.

Remaining scenarios stay active follow-on work with their own reviewed samples and
data-gap acceptance. This increment is not completion of every statutory form.

## Form E: first working preview

The owner accepted both facing portrait A4 and single-sheet landscape A4 layouts
on 30 September; the local preview offers a selector. The local read-only
register uses licence/series/date filters, original paid-out evidence and each
recorded payment/closure through the selected business-date cutoff. Unpaid
approvals are excluded; current ACTIVE status does not filter out closed histories.
Imported openings retain explicit pre-cutover-history warnings. Closed archive
claims lack normalized licence/series mapping and are counted separately, not
silently combined with operational loans. No current Party address, metal price,
remaining balance or arbitrary owner/recipient address supplies a missing original.

The working preview has at most five ordinary entries per facing pair or landscape
sheet, long-entry continuation pages and an evidence appendix. It assigns no pages.
The deployed book workflow now saves immutable full/partial batches, permanent
physical page ranges and exact private PDFs after administrator source review.
Unknowns remain explicit; unsupported origins/renewals and ambiguous payouts block
finalisation. Daily activity supports handwritten updates by business/recording date.
Physical acceptance, branch book opening and reviewed Tamil headings remain pending.
See [field mapping and next work](../implementation/form-e-pledge-book.md).
