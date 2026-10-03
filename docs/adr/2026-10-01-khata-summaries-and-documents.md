---
status: accepted
owner: loans
updated: 2026-10-01
tags: [khata, summaries, documents, rls]
related: [2026-10-01-khata-agreement-design.md, ../architecture/khata-technical-design.md, ../implementation/khata-integration.md]
---

# Khata summary composition and preserved source documents

The owner authorized local borrower/dashboard, document and summary integration.
This decision does not authorize a production migration or workspace pilot.

Compose typed pawn and khata rows in a new shared Party selector. Preserve the
pawn-only selector contract, routes, event fold, collection calculator and print
workflows. Borrower totals include actual khata principal and accrued unpaid
interest, including unbilled annual interest and the original opening minimum.
Agreed limits and unused entitlement are never borrower debt. Totals precede
display limits/pagination; unavailable evidence cannot become a partial total.

Dashboard active borrower counts use the union of identities across both kinds.
Principal combines actual outstanding principal. Recorded ordinary-loan interest
retains its meaning; khata accrued, due and overdue interest appear separately.
Saved ordinary-loan health and activity reports retain their original scope and
are labelled accordingly. Financially settled khatas do not count as active
debt, while outgoing reservations remain visible until actual handover.

The register/detail use khata routes and never send a khata PK to pawn servicing.
Same-day collateral cover is a separate read-only suggestion, excluding reserved
outgoing items. Missing prices do not make known debt unavailable. Confirmation
commands remain responsible for all permission, billing, photo, price and lending
checks. Both licence-associated and independent series appear in shared reads.

Use one directly Workspace-owned `KhataDocumentIssue` table for immutable
`khata-document/1` snapshots and private A4 PDF bytes. Documents reference their
own account and optional typed source operation. Source vouchers replay only the
source prefix for principal, entitlement, agreement and custody; later changes
cannot substitute live terms. Issuance records current borrower contact identity
explicitly. An existing correction is disclosed at issuance, and later corrections
appear alongside the preserved issue in the account history. Independent documents
retain explicit lender identity and explicit absence of a licence; associated
documents retain reviewed licence/revision evidence. Initial collateral sources
without approved lender evidence do not get an invented historical agreement.

Statements snapshot today's canonical balances and source sequence; historical
or future balance reconstruction is not implied. Source documents carry their
original business date and a separate issuance timestamp. Complete text flows
across A4 pages using the existing shaped Unicode engine and ReportLab page
furniture. A bounded renderer fails instead of issuing a truncated document.

Issuance is a CSRF-protected POST requiring `data.view`, `data.edit`, `data.export`
and business write availability. A locked account and workspace-unique request
UUID provide consistent, idempotent snapshots. Downloads are authenticated,
Workspace-scoped GETs requiring `data.export`, with private/no-store headers.
Verify payload and PDF SHA-256 plus byte size before returning stored bytes;
never regenerate a missing or corrupt original. SQL enforces forced RLS,
immutability, parent identity, source/effective agreement, position prefix and
licence association. Register the new file with retained storage inventory.

Verified borrower portal summaries include both kinds and net khata receipts;
payment history is informational because outstanding already reflects receipts.
Do not subtract those receipts twice. This does not publish staff khata PDFs or
introduce a public file URL. Native recovery, remaining operational command forms,
item labels/statutory/default boundaries, unsupported corrections and pilot review
remain distinct release work.

## Source-backed read pruning follow-up (2 October)

Measured local performance justifies a balance-only prefetch profile, lazy detail
panels, database register scope filters and bounded custody rendering. This does
not introduce a stored projection/cache or change the financial calculator.
Position replay keeps every WITHDRAW/REVISE/SETTLE source, activated agreements,
saved periods and uncorrected allocations. Live correlated custody counts retain
forced RLS and direct Workspace scope. Complete-source/compact equivalence is tested
through compensation, revised terms and settlement/physical closure. Any future
financial source kind must extend the canonical fold and compact feed together.
Totals/attention still evaluate all matched accounts before display pagination.
Exact UUID/QR/history links select an item across custody pages; saved PDFs and
printed scan routes retain their identity. See the
[performance checkpoint](../implementation/khata-read-performance.md).

## Collection and readable event follow-up (2 October)

Collection attention reuses today's canonical compact summaries. Next-anniversary
amounts are explicitly forward estimates using activated terms and existing
KHATA-1 interest schedule, grouped by contractual due date. They never replace
current balances, freeze charges or allow advance receipt. Date windows filter
attention, not economic terms; oldest unpaid dates govern overdue days. Totals
precede paging and unavailable evidence cannot become zero. Current price-based
LTV and recorded exchange warnings remain distinct facts. Read-only event pages
use exact typed saved source relationships/values, with no current revaluation.
No new persistence or posting/notification architecture is introduced. Optional
reminders retain a separately reviewed Loans-intent/Notify boundary. See the
[implementation checkpoint](../implementation/khata-collection-worklist.md).
