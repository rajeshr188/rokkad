---
status: accepted
owner: project
updated: 2026-09-30
tags: [loans, auctions, fw-013]
---

# Preserve the auctioneer's original cohort and reviewed versions

Branches give the auctioneer a list, post the notices they prepare, record later
collections/releases, then return the remaining-loan list. The owner selected this
administrative handover as the next FW-013 increment. It must not become a second
auction lifecycle or a substitute for per-loan statutory evidence.

Use two ordinary Loans-owned models: immutable `AuctioneerHandover` fixes the
licence, intended recipient and original loan IDs; immutable
`AuctioneerHandoverRevision` preserves every original loan's current particulars,
recorded balances, custody, readiness checks, inclusion decision, review note,
actor and time. A bounded JSON snapshot avoids a mutable batch-membership subsystem.
Both models have direct Workspace ownership, forced RLS and SQL update/delete
rejection. Insert guards validate parent scope, original loan membership, complete
revision coverage and consecutive version numbers. Registry coverage is mandatory.

Administrators paste up to 100 complete loan numbers within one licence. Preview
does not write. A signed one-hour review is bound to Workspace, actor, cohort,
inputs and a current-state digest. Saving rechecks authority/commercial write
access, serializes the licence/list and locks source loans and auctions, then
reprojects. A changed state or intervening saved version invalidates confirmation.
NOWAIT source locks avoid cycles with financial/auction writers; a busy source
requires refresh. Identical retries return the saved revision; changed instructions
under the same request identity fail.

Remaining-loan candidates follow the existing active/overdue auction-initiation
check and must have recorded debt and all original collateral in the vault.
Closed, settled, changed-licence, partial-release/custody and missing-balance rows
stay in reconciliation but cannot be selected. This is operational screening,
not legal eligibility. Prior manual omissions remain unselected until explicitly
reinstated; an empty subsequent remaining list is valid. Canonical balance readers
supply principal, recorded interest and fees; unposted interest is not invented.
Current default contacts are labelled as such, not verified service addresses.

Printable landscape HTML and CSV are rendered from saved facts. The printout also
lists withheld/removed references. Browser layout may vary: unlike Form E, this
administrative output does not promise byte-identical PDF reprints or permanent
statutory page numbers. No new media FileField is needed. Private export requires
administration plus `data.export`, is hash-checked and no-store; CSV neutralizes
formula-leading text. Sending, posting, custody, auction initiation/cancellation,
start/completion and money remain separate existing actions.

The original cohort cannot grow. Further loans or licences use another list;
saved evidence cannot be edited or deleted. A prescribed multi-pledge catalogue,
auctioneer portal/integration and automatic sending remain outside this increment.
