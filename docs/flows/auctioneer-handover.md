---
status: active
owner: project
updated: 2026-09-30
tags: [loans, auctioneer, staff-guide, fw-013]
---

# Auctioneer handover and remaining-loan review

Workspace administrators use **Reports → Statutory forms & notices → Auctioneer
handover lists**. This is an administrative list for manual coordination, not an
auction permission, statutory notice or proof of service.

1. Review your overdue loans. Choose one licence, name the list and intended
   auctioneer, and paste full loan numbers (prefixes and leading zeroes included),
   one per line or comma-separated. Up to 100 loans can belong to a list; use
   another list for additional loans or licences.
2. Preview. Check the borrower, current default address/contact, recorded balances,
   articles, custody and any existing auction/readiness checks. On-hold rows cannot
   be included. You may withhold another remaining loan; explain why in the review
   note. Missing contact particulars remain explicit and must be checked before
   notices are prepared.
3. Confirm to save version 1. Print the landscape list (or save it as PDF through
   your browser) or download CSV and share manually with the intended auctioneer.
   Printing does not record sending or transfer of collateral. Downloads contain
   customer information; use the intended business recipient.
4. Continue the existing per-loan auction/statutory workflow. Attach the actual
   signed notice supplied by the auctioneer to its printing evidence, record postal
   handling, and review statutory readiness separately.
5. After collections, releases or follow-ups, reopen the same list. All original
   loans remain visible. Changed balances, loan/custody states, contact particulars,
   financial activity and readiness are highlighted against the previous version.
   Closed/settled/held loans drop out of the selectable remaining list. Previously
   manually withheld loans remain unticked until explicitly reselected.
6. Review, add a note and save an updated version. Share the newest version; the
   printout identifies removed/withheld references as well as remaining loans. An
   empty remaining list is valid after all loans have been resolved. Refresh and
   reconcile again after any later activity and before sale.

If a loan changes while you are reviewing, saving is rejected so you can review
fresh facts. Identical repeated submissions return the same version. A review
expires after one hour. Every saved version records its reviewer/time and preserves
its own data; it is not silently refreshed when downloaded later. Print appearance
can change with browser settings; these are not preserved Form E PDF artifacts.

Amounts are canonical **recorded** principal, interest and fees as of the review
date; this is not a final settlement quotation including unposted interest. Partial
returns or unclear custody need separate review. Neither omission from a handover
nor a loan closure automatically withdraws/cancels an existing notice or auction.
Use its existing workflow explicitly. Sale start/completion still enforce their
existing statutory and financial checks.

See [statutory notices](statutory-auction-notices.md) and
[the architecture decision](../adr/2026-09-30-auctioneer-handover-reconciliation.md).
