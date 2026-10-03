---
status: accepted
owner: project
updated: 2026-09-30
tags: [loans, statutory, notices, fw-013]
---

# Statutory auction service is Loans evidence, independent of digital reminders

The owner selected the manual postal workflow after review found that auction start
accepted a Notify job marked SENT as its notice gate. Provider acceptance cannot
establish the published Tamil Nadu postal-service requirements.

Loans now owns a preserved auction catalogue and append-only handling evidence.
Ordinary Django models/services/forms implement preparation, preview, preserved
issuance, printing, postal dispatch, acknowledgement or returned-cover follow-up,
administrator readiness review and withdrawal. Notify remains independent and is
not consulted by auction readiness. Courtesy digital reminders are optional at
auction initiation. The existing operational reference PDF remains available.

`StatutoryAuctionNotice` owns the frozen particulars and exact PDF; one notice
belongs to one auction attempt. `StatutoryNoticeEvidence` records the actual event
date separately from creation time and signed-in actor. Replayed identical requests
return the original rows; changed instructions fail. Corrections require withdrawal,
cancellation and a fresh auction attempt; existing files/rows are never overwritten.
An auction lock serializes notice generation, evidence recording and start/complete.

Both tables have direct non-null Workspace ownership, forced RLS, cross-parent
Workspace guards and SQL update/delete rejection. Evidence files are private,
content-validated, hashed, retained and included in storage reference inventory.
Downloads resolve the Workspace and administrator permission before reading bytes,
verify the hash, and return no-store responses. No public storage URLs are exposed.

The published-rule operational baseline requires postal dispatch at least 45 days
before sale, acknowledgement/POD or the returned-notice official certificate route,
and a current administrator review. Returned-notice referral/official receipt/
affixture/certification dates remain distinct. Late facts are recorded but cannot
clear a missed deadline. Review captures permission, schedule/deviation authority,
two newspaper publications, police catalogue dispatch and the responsible operator's
checks of distribution, objections, attendance arrangements and valuation.
The start and completion commands both require readiness on the advertised day;
pre-existing open auctions are not grandfathered by a digital SENT job. Completed
historical evidence and reversal behavior are preserved.

The gate establishes recorded operational evidence, not government authorization or
automated legal certification. Current amendments, prescribed language, authority
directions and document adequacy still require qualified review. First catalogue
headings are English, with Unicode/Tamil particulars shaped by the installed
PyMuPDF renderer. Reviewed Tamil statutory wording and the remaining form generators
stay explicit delivery work, not hidden behind a claim that all forms are complete.

No new queue, messaging provider, automatic postal booking, automatic borrower
contact or accounting subsystem is introduced. See the
[delivery plan](../plans/statutory-forms-and-notices.md) and
[operator guide](../flows/statutory-auction-notices.md).
