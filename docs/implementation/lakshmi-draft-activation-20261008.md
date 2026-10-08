---
status: completed
owner: project
updated: 2026-10-08
tags: [loans, operations, origination, correction]
---

# Lakshmi D01622 and D01623: record actual paper payouts

On 8 October the owner asks to correct or delete the two drafts because activation
fails. Read-only production inspection under the restricted role identifies an
unpaid digital draft for D01622 and a fully reversed native payout for D01623.
These require different existing admission services; directly assigning ACTIVE
would leave balances and source history incorrect.

D01623 uses the previously owner-confirmed actual paper agreement: 24 September,
2,100 principal, 4% monthly, three months, 84 advance interest, 10 document charge
and 2,006 paid. The separate production correction is now explicitly authorized.
The owner separately confirms D01622's actual paper payout: 2 October, 3,000
principal, 4% monthly, three months, 120 advance interest, 10 document charge and
2,870 paid. Current twelve-month defaults do not replace these actual terms.

Signed rollback previews reconcile both before recording. D01623 uses existing
recorded-origination-correction/1, retaining the original same-day native
payout/reversal pair 19388/19390 and approval, collateral identity and photographs.
D01622 uses ordinary completed-payout admission on its unpaid draft. Both use
existing recorded-history commands, owner action checks and forced RLS. Neither
represents another physical payout now. No row is manually assigned ACTIVE and no
original posted evidence is edited or deleted.

D01623 commits at 13:19:13 UTC (18:49:13 IST), D01622 at 13:19:22 UTC (18:49:22 IST).
Both are ACTIVE, retain their loan numbers and IDs, and have exactly one unreversed
financial origin. Command retries create no duplicates. Recorded principal is
2,100/3,000 respectively, with zero interest outstanding on 8 October. Boundary
checks establish D01623's next 84 charge on 25 October and D01622's next 120 charge
on 3 November; their anniversary dates remain covered by advance interest.

Independent repeatable-read/read-only verification confirms ordinary list/detail,
repayment and release GETs return 200 for both loans, and document projections
validate. No sessions, new document issues, notifications or additional financial
posts occur during verification. No-context and cross-Workspace isolation remain.
A current complete-paper-book claim is not inferred or posted from confirming the
original payouts; later receipts continue through ordinary servicing.

Private before-images, actual agreement reviews, operator source and execution/
verification logs stay under /home/rokkad/deploy/draft-repair-20261008 on the server.
No borrower identity, photographs, rendered customer pages or full database copy
is downloaded locally. This is a scoped data correction through already-deployed
services, not a software/image/migration deployment. It supersedes statements that
production D01623 remained uncorrected; older LO-01/LO-05/LO-07 evidence retains its
dated staging/deployment scope.
